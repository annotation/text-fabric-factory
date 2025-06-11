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
PAGES = "pages"
SCANS = "scans"
SCANINFO = "scanInfo"
THUMB = "thumb"
SCAN_COMMAND = "/opt/homebrew/bin/magick"
SIZES_COMMAND = "/opt/homebrew/bin/identify"
SIZES_OPTIONS = ["-ping", "-format", "%w %h"]

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
            currend directory.
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
        pageInDir = f"{scanDir}/{PAGES}"
        logoInDir = f"{scanDir}/{LOGO}"

        self.scanDir = scanDir
        self.scanInfoDir = scanInfoDir
        self.thumbDir = thumbDir
        self.pageInDir = pageInDir
        self.logoInDir = logoInDir

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
        logoInDir = self.logoInDir

        settings = self.settings
        scanExt = settings.scanExt

        plabel = "originals"
        dlabel = "thumbnails"

        srcDir = f"{scanDir}/{PAGES}"
        dstDir = f"{thumbDir}/{PAGES}"
        thumbLogoDir = f"{thumbDir}/{LOGO}"
        scanInfoLogoDir = f"{scanInfoDir}/{LOGO}"
        sizesFileThumb = f"{thumbDir}/sizes_{PAGES}.tsv"
        sizesFileScans = f"{scanDir}/sizes_{PAGES}.tsv"
        sizesFileScanInfo = f"{scanInfoDir}/sizes_{PAGES}.tsv"

        if force or not dirExists(scanInfoDir):
            dirRemove(scanInfoDir)
            dirMake(scanInfoDir)
            dirCopy(logoInDir, scanInfoLogoDir)
            console("Initialized scanInfo dir")
        else:
            console("scanInfo dir already present")

        if force or not dirExists(thumbLogoDir):
            dirRemove(thumbLogoDir)
            dirCopy(logoInDir, thumbLogoDir)

        if force or not dirExists(dstDir):
            self.doThumb(srcDir, dstDir, scanExt.orig, scanExt.thumb, plabel, dlabel)
        else:
            if verbose == 1:
                console(f"Already present: {dlabel} ({PAGES})")

        if force or not fileExists(sizesFileThumb):
            self.doSizes(dstDir, scanExt.thumb, sizesFileThumb, dlabel)
        else:
            if verbose == 1:
                console(f"Already present: sizes file {dlabel} ({PAGES})")

        if force or not fileExists(sizesFileScans):
            self.doSizes(srcDir, scanExt.orig, sizesFileScans, plabel)
        else:
            if verbose == 1:
                console(f"Already present: sizes file {plabel} ({PAGES})")

        if force or not fileExists(sizesFileScanInfo):
            fileCopy(sizesFileScans, sizesFileScanInfo)
            console("Copied sizes file to scanInfo")
        else:
            console("sizes file already present in scanInfo")

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
            console(f"{label}: {nFiles}")

    def doSizes(self, imDir, ext, sizesFile, label):
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

        console(f"\tGet sizes of {len(items)} {label} ({PAGES})")
        j = 0
        nItems = len(items)

        sizes = []

        for i, (base, fromFile) in enumerate(sorted(items)):
            if j == 100:
                perc = int(round(i * 100 / nItems))

                if verbose == 1:
                    console(f"\t\t{perc:>3}% done")

                j = 0

            status = run(
                [SIZES_COMMAND] + SIZES_OPTIONS + [fromFile], capture_output=True
            )
            j += 1

            if status.returncode != 0:
                console(status.stderr.decode("utf-8"), error=True)
            else:
                (w, h) = status.stdout.decode("utf-8").strip().split()
                sizes.append((base, w, h))

        perc = 100

        if verbose == 1:
            console(f"\t\t{perc:>3}% done")

        with open(sizesFile, "w") as fh:
            fh.write("file\twidth\theight\n")

            for file, w, h in sizes:
                fh.write(f"{file}\t{w}\t{h}\n")

    def doThumb(self, fromDir, toDir, extIn, extOut, plabel, dlabel):
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

        console(f"\tConvert {len(items)} {plabel} to {dlabel} ({PAGES})")

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
