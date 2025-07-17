from subprocess import run

from tf.core.files import (
    initTree,
    getLocation,
    expanduser as ex,
    dirContents,
    dirExists,
    dirRemove,
    dirCopy,
    dirMake,
    fileExists,
    fileCopy,
    extNm,
    fileRemove,
)
from tf.core.helpers import console, readCfg

from .iiif import FILE_NOT_FOUND


LOGO = "logo"
SCANS = "scans"
SCANINFO = "scanInfo"
THUMB = "thumb"
SCAN_COMMAND = "/opt/homebrew/bin/magick"
IDENTIFY_COMMAND = "/opt/homebrew/bin/identify"
SIZES_OPTIONS = ["-ping", "-format", "%w %h"]
COLORSPACE_OPTIONS = ["-ping", "-format", "%[colorspace]"]

DS_STORE = ".DS_Store"


class Scans:
    def __init__(
        self,
        verbose=0,
        force=False,
        backend=None,
        org=None,
        repo=None,
        relative=None,
        sourceBase=None,
    ):
        """Process scans into thumbnails and detect sizes

        Parameters
        ----------
        backend, org, repo, relative: string, optional None
            If all of these are None, these parameters are derived from the
            current directory.
            If one of them is not None, all four of them are taken from the parameters,
            and the current directory is not used to determine them.
        repoDir: string, optional None
            Directory under which the `scans` directory with scans resides.
            Normally is is computed from the backend, org, repo parameters
            or the location of the current directory, but you can override it
            with this parameter.

        """
        if all(s is None for s in (backend, org, repo, relative)):
            (backend, org, repo, relative) = getLocation()
            base = ex(f"~/{backend}")
            repoDir = f"{base}/{org}/{repo}"
        else:
            repoDir = sourceBase

        if any(s is None for s in (backend, org, repo, relative)):
            console(
                (
                    "Not working in a repo: "
                    f"backend={backend} org={org} repo={repo} relative={relative}"
                ),
                error=True,
            )
            self.good = False
            return

        refDir = f"{repoDir}{relative}"
        sourceRefDir = sourceBase if sourceBase else refDir

        if verbose == 1:
            console(
                f"Working in repository {org}/{repo}{relative} in back-end {backend}"
            )
            console(f"Source dir = {sourceRefDir}")

        self.good = True

        (ok, settings) = readCfg(
            refDir, "scans", "imageprep", verbose=verbose, plain=False
        )
        if not ok:
            self.good = False
            return

        self.settings = settings

        scanDir = f"{sourceRefDir}/{SCANS}"
        scanInfoDir = f"{sourceRefDir}/{SCANINFO}"
        thumbDir = f"{sourceRefDir}/{THUMB}"

        self.scanDir = scanDir
        self.scanInfoDir = scanInfoDir
        self.thumbDir = thumbDir

        self.verbose = verbose
        self.force = force

    def process(self, force=False):
        if not self.good:
            return

        if force is None:
            force = self.force

        verbose = self.verbose
        scanDir = self.scanDir
        scanInfoDir = self.scanInfoDir
        thumbDir = self.thumbDir

        settings = self.settings
        scanExt = settings.scanExt

        plabel = "originals"
        dlabel = "thumbnails"

        for dstDir in (scanInfoDir, thumbDir):
            if force or not dirExists(dstDir):
                dirRemove(dstDir)
                dirMake(dstDir)

            if verbose == 1:
                console(f"Initialized {dstDir}")
            else:
                if verbose == 1:
                    console(f"{dstDir} already present")

        (srcFiles, srcSubDirs) = dirContents(scanDir)

        for fl in srcFiles:
            if fl == DS_STORE or fl.startswith("sizes_"):
                continue

            srcFl = f"{scanDir}/{fl}"
            dstFl = f"{thumbDir}/{fl}"
            fileCopy(srcFl, dstFl)

            if verbose:
                console(f"Copied top level file {fl}")

        for sbd in srcSubDirs:
            console(f"{sbd}:")

            srcDir = f"{scanDir}/{sbd}"

            if sbd == LOGO:
                for dstDir in (f"{thumbDir}/{sbd}", f"{scanInfoDir}/{sbd}"):
                    if force or not dirExists(dstDir):
                        dirRemove(dstDir)
                        dirCopy(srcDir, dstDir)

                        if verbose:
                            console(f"\tCopied subdirectory {sbd}")

            else:
                sizesFileThumb = f"{thumbDir}/sizes_{sbd}.tsv"
                sizesFileScans = f"{scanDir}/sizes_{sbd}.tsv"
                sizesFileScanInfo = f"{scanInfoDir}/sizes_{sbd}.tsv"
                colorspacesFileScans = f"{scanDir}/colorspaces_{sbd}.tsv"
                colorspacesFileScanInfo = f"{scanInfoDir}/colorspaces_{sbd}.tsv"

                if force or not dirExists(dstDir):
                    self.doThumb(
                        sbd,
                        srcDir,
                        dstDir,
                        scanExt.orig,
                        scanExt.thumb,
                        plabel,
                        dlabel,
                    )
                else:
                    if verbose == 1:
                        console(f"\tAlready present: {dlabel} ({sbd})")

                if force or not fileExists(sizesFileThumb):
                    self.doSizes(sbd, dstDir, scanExt.thumb, sizesFileThumb, dlabel)
                else:
                    if verbose == 1:
                        console(f"\tAlready present: sizes file {dlabel} ({sbd})")

                if force or not fileExists(sizesFileScans):
                    self.doSizes(sbd, srcDir, scanExt.orig, sizesFileScans, plabel)
                else:
                    if verbose == 1:
                        console(f"\tAlready present: sizes file {plabel} ({sbd})")

                if force or not fileExists(sizesFileScanInfo):
                    fileCopy(sizesFileScans, sizesFileScanInfo)
                    console(f"\tCopied sizes_{sbd} file to scanInfo")
                else:
                    console(f"\tsize_{sbd} file already present in scanInfo")

                if force or not fileExists(colorspacesFileScans):
                    self.doColorspaces(
                        sbd, srcDir, scanExt.orig, colorspacesFileScans, plabel
                    )
                else:
                    if verbose == 1:
                        console(f"\tAlready present: colorspaces file {plabel} ({sbd})")

                if force or not fileExists(colorspacesFileScanInfo):
                    self.doColorspaces(
                        sbd, srcDir, scanExt.orig, colorspacesFileScanInfo, plabel
                    )
                else:
                    console(f"\tcolorspaces_{sbd} file already present in scanInfo")

                for folder, label, ext in (
                    (srcDir, plabel, scanExt.orig),
                    (dstDir, dlabel, scanExt.thumb),
                ):
                    notFound = f"{FILE_NOT_FOUND}.{ext}"
                    files = [
                        f
                        for f in dirContents(folder)[0]
                        if f not in {DS_STORE, notFound} and extNm(f) == ext
                    ]
                    nFiles = len(files)
                    console(f"\t{label}: {nFiles}")

    def doSizes(self, sbd, imDir, ext, sizesFile, label):
        if not self.good:
            return

        verbose = self.verbose
        fileRemove(sizesFile)

        fileNames = dirContents(imDir)[0]
        items = []

        for fileName in sorted(fileNames):
            if fileName == DS_STORE:
                continue

            thisExt = extNm(fileName)

            if thisExt != ext:
                continue

            base = fileName.removesuffix(f".{thisExt}")
            items.append((base, f"{imDir}/{fileName}"))

        console(f"\t\tGet sizes of {len(items)} {label} ({sbd})")
        j = 0
        nItems = len(items)

        sizes = []

        for i, (base, fromFile) in enumerate(sorted(items)):
            if j == 100:
                perc = int(round(i * 100 / nItems))

                if verbose == 1:
                    console(f"\t\t\t{perc:>3}% done")

                j = 0

            status = run(
                [IDENTIFY_COMMAND] + SIZES_OPTIONS + [fromFile], capture_output=True
            )
            j += 1

            if status.returncode != 0:
                console(f"\t{status.stderr.decode('utf-8')}", error=True)
            else:
                (w, h) = status.stdout.decode("utf-8").strip().split()
                sizes.append((base, w, h))

        perc = 100

        if verbose == 1:
            console(f"\t\t\t{perc:>3}% done")

        with open(sizesFile, "w") as fh:
            fh.write("file\twidth\theight\n")

            for file, w, h in sizes:
                fh.write(f"{file}\t{w}\t{h}\n")

    def doColorspaces(self, sbd, imDir, ext, colorspacesFile, label):
        if not self.good:
            return

        verbose = self.verbose
        fileRemove(colorspacesFile)

        fileNames = dirContents(imDir)[0]
        items = []

        for fileName in sorted(fileNames):
            if fileName == DS_STORE:
                continue

            thisExt = extNm(fileName)

            if thisExt != ext:
                continue

            base = fileName.removesuffix(f".{thisExt}")
            items.append((base, f"{imDir}/{fileName}"))

        console(f"\t\tGet colorspaces of {len(items)} {label} ({sbd})")
        j = 0
        nItems = len(items)

        colorspaces = []

        for i, (base, fromFile) in enumerate(sorted(items)):
            if j == 100:
                perc = int(round(i * 100 / nItems))

                if verbose == 1:
                    console(f"\t\t\t{perc:>3}% done")

                j = 0

            status = run(
                [IDENTIFY_COMMAND] + COLORSPACE_OPTIONS + [fromFile],
                capture_output=True,
            )
            j += 1

            if status.returncode != 0:
                console(f"\t{status.stderr.decode('utf-8')}", error=True)
            else:
                colorspace = status.stdout.decode("utf-8").strip()
                colorspaces.append((base, colorspace))

        perc = 100

        if verbose == 1:
            console(f"\t\t\t{perc:>3}% done")

        with open(colorspacesFile, "w") as fh:
            fh.write("file\tcolorspace\n")

            for file, colorspace in colorspaces:
                fh.write(f"{file}\t{colorspace}\n")

    def doThumb(self, sbd, fromDir, toDir, extIn, extOut, plabel, dlabel):
        if not self.good:
            return

        verbose = self.verbose
        settings = self.settings
        quality = settings.scanQuality
        resize = settings.scanResize

        scanOptions = ["-quality", quality, "-resize", resize]

        initTree(toDir, fresh=True)

        fileNames = dirContents(fromDir)[0]
        items = []

        for fileName in sorted(fileNames):
            if fileName == DS_STORE:
                continue

            thisExt = extNm(fileName)
            base = fileName.removesuffix(f".{thisExt}")

            if thisExt != extIn:
                continue

            items.append((base, f"{fromDir}/{fileName}", f"{toDir}/{base}.{extOut}"))

        console(f"\tConvert {len(items)} {plabel} to {dlabel} ({sbd})")

        j = 0
        nItems = len(items)

        for i, (base, fromFile, toFile) in enumerate(sorted(items)):
            if j == 100:
                perc = int(round(i * 100 / nItems))

                if verbose == 1:
                    console(f"\t\t{perc:>3}% done")

                j = 0

            run([SCAN_COMMAND] + [fromFile] + scanOptions + [toFile])
            j += 1

        perc = 100

        if verbose == 1:
            console(f"\t\t{perc:>3}% done")
