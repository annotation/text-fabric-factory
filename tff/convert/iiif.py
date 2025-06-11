import collections

from tf.core.files import (
    writeJson,
    fileOpen,
    fileExists,
    fileCopy,
    initTree,
    dirNm,
    dirExists,
    dirRemove,
    dirCopy,
    dirContents,
    dirMake,
    stripExt,
    abspath,
)
from tf.core.generic import AttrDict
from tf.core.helpers import console, readCfg
from .helpers import getPageInfo, getImageLocations, getImageSizes

DS_STORE = ".DS_Store"

FILE_NOT_FOUND = "filenotfound"
FILE_NOT_FOUND_SIZES = (480, 640)


def fillinIIIF(data, **kwargs):
    tpd = type(data)

    if tpd is str:
        for k, v in kwargs.items():
            pattern = "{" + k + "}"

            if type(v) is int and data == pattern:
                data = v
                break
            else:
                data = data.replace(pattern, str(v))

        return data

    if tpd is list:
        return [fillinIIIF(item, **kwargs) for item in data]

    if tpd is dict:
        return {k: fillinIIIF(v, **kwargs) for (k, v) in data.items()}

    return data


def parseIIIF(settings, prod, selector, **kwargs):
    """Parse the iiif yml file and deliver a filled in section.

    The iiif.yml file contains switches and constants and macros which then are used
    to define IIIF things via templates.

    The top-level section `scans` contains instructions to define extra annotations
    on node types that need to refer to scans.
    This is only used for WATM generation.

    The top-level section `templates` contains fragments from which manifests can be
    constructed. This is only used in this module.

    This function fills in the switches, based on the parameter `prod`, then
    prepares the constants, then prepares the macros, and then uses it all
    to assemble either the `scans` section or the `templates` section; this
    choice is based on the parameter `selector`.

    Parameters
    ----------
    prod: string
        Either `prod` or `dev` or `preview`.
        This determines whether we fill in a production value or a develop value
        or a preview value for each of the settings mentioned in the `switches`
        section of the iiif.yml file.
    selector: string
        Either `scans` or `templates` or `excludedFolders`.
        Which top-level of sections we are going to grab out of the iiif.yml file.
    kwargs: dict
        Additional optional parameters to pass as key value pairs to
        the iiif config file. These values will be filled in for place holders
        of the form `[`*arg*`]`.
    """

    def applySwitches(prod, constants, switches):
        if len(switches):
            for k, v in switches[prod].items():
                constants[k] = v

        return constants

    def substituteConstants(data, macros, constants, kwargs):
        tpd = type(data)

        if tpd is str:
            for k, v in macros.items():
                pattern = f"<{k}>"
                data = data.replace(pattern, str(v))

            for k, v in constants.items():
                pattern = f"«{k}»"

                if type(v) is int and data == pattern:
                    data = v
                    break
                else:
                    data = data.replace(pattern, str(v))

            if type(data) is str:
                for k, v in kwargs.items():
                    pattern = f"[{k}]"

                    if type(v) is int and data == pattern:
                        data = v
                        break
                    else:
                        data = data.replace(pattern, str(v))

            return data

        if tpd is list:
            return [
                substituteConstants(item, macros, constants, kwargs) for item in data
            ]

        if tpd is dict:
            return {
                k: substituteConstants(v, macros, constants, kwargs)
                for (k, v) in data.items()
            }

        return data

    constants = applySwitches(
        prod, settings.get("constants", {}), settings.get("switches", {})
    )
    macros = applySwitches(
        prod, settings.get("macros", {}), settings.get("switches", {})
    )

    return AttrDict(
        {
            x: substituteConstants(xText, macros, constants, kwargs)
            for (x, xText) in settings.get(selector, {}).items()
        }
    )


class IIIF:
    def __init__(
        self,
        teiVersion,
        app,
        pageInfoDir,
        outputDir=None,
        prod="dev",
        silent=False,
        **kwargs,
    ):
        """Class for generating IIIF manifests.

        Parameters
        ----------
        teiVersion: string
            Subdirectory within the static directory.
            The manifests are generated in this subdirectory, which corresponds to
            the version of the TEI source.
        app: object
            A loaded TF data source
        pageInfoDir: string
            Directory where the files with page information are, especially the
            page sequence file.
        outputDir: string, optional None
            If present, manifests nad logo will be generated in this directory.
            Otherwise a standard location is chosen: `static` at
            the top-level of the repo and within that `prod` or `dev` or `preview`
        prod: string, optional dev
            Whether the manifests are for production (`prod`) or development (`dev`)
            or preview (`preview`)
            If the value is `preview` we assume that the actual scans are in a IIIF
            repo, and not within reach of the code here. But we do assume
            that a sizes file is present in the expected location (in the scanRefDir),
            and possibly a rotations file.
        silent: boolean, optional False
            Whether to suppress output messages
        kwargs: dict
            Additional optional parameters to pass as key value pairs to
            the iiif config file. These values will be filled in for place holders
            of the form `[`*arg*`]`.
        """
        self.teiVersion = teiVersion
        self.app = app
        self.pageInfoDir = pageInfoDir
        self.prod = prod if prod in {"prod", "dev", "preview"} else "dev"
        self.silent = silent
        self.error = False
        self.kwargs = kwargs

        teiVersionRep = f"/{teiVersion}" if teiVersion else teiVersion

        F = app.api.F
        L = app.api.L

        myDir = dirNm(abspath(__file__))
        self.myDir = myDir

        locations = getImageLocations(app, prod, silent)
        repoLocation = locations.repoLocation
        self.thumbDir = locations.thumbDir
        scanRefDir = locations.scanRefDir
        self.scanRefDir = scanRefDir
        self.coversDir = locations.coversDir
        doCovers = locations.doCovers
        self.doCovers = doCovers

        self.console(f"Scan images taken from {scanRefDir}")

        outputDir = (
            f"{repoLocation}/static{teiVersionRep}/{prod}"
            if outputDir is None
            else outputDir
        )
        self.outputDir = outputDir
        self.manifestDir = f"{outputDir}/manifests"

        self.pagesDir = f"{scanRefDir}/pages"
        self.logoInDir = f"{scanRefDir}/logo"
        self.logoDir = f"{outputDir}/logo"

        self.miradorHtmlIn = f"{myDir}/mirador.html"
        self.miradorHtmlOut = f"{outputDir}/mirador.html"

        if doCovers:
            self.coversHtmlIn = f"{repoLocation}/programs/covers.html"
            self.coversHtmlOut = f"{outputDir}/covers.html"

        (ok, settings) = readCfg(
            repoLocation, "iiif", "IIIF", verbose=-1 if silent else 1, plain=True
        )
        if not ok:
            self.error = True
            return

        self.settings = settings
        manifestLevel = settings.get("manifestLevel", "folder")
        console(f"Manifestlevel = {manifestLevel}")
        self.manifestLevel = manifestLevel

        excludedFolders = parseIIIF(settings, prod, "excludedFolders")
        self.excludedFolders = excludedFolders
        self.mirador = parseIIIF(settings, prod, "mirador", **kwargs)
        self.templates = parseIIIF(
            settings, prod, "templates", **kwargs
        )
        switches = parseIIIF(settings, prod, "switches", **kwargs)
        server = switches[prod]["server"]
        console(f"All generated urls are for a {prod} deployment on {server}")

        folders = (
            [F.folder.v(f) for f in F.otype.s("folder")]
            if manifestLevel == "folder"
            else [
                (F.folder.v(fo), [F.file.v(fi) for fi in L.d(fo, otype="file")])
                for fo in F.otype.s("folder")
            ]
        )

        self.getSizes()
        self.getRotations()
        self.getPageSeq()
        pages = self.pages
        properPages = pages.get("pages", {})
        self.folders = folders
        mLevelFolders = manifestLevel == "folder"

        self.console("Collections:")

        for item in folders:
            folder = item if mLevelFolders else item[0]

            n = len(properPages[folder]) if folder in properPages else 0
            m = (
                None
                if mLevelFolders
                else (
                    sum(len(x) for x in properPages[folder].values())
                    if folder in properPages
                    else 0
                )
            )

            nP = n if mLevelFolders else m
            nF = m if mLevelFolders else n

            pageRep = f"{nP:>4} pages"
            fileRep = "" if nF is None else f"{nF:>4} files and "

            if excludedFolders.get(folder, False):
                self.console(
                    f"{folder:>10} with {fileRep}{pageRep} (excluded in config)"
                )
                continue

            if folder not in properPages:
                console(
                    f"{folder:>10} with {fileRep}{pageRep} (not excluded in config)",
                    error=True,
                )
                self.error = True
                continue

            self.console(f"{folder:>10} with {fileRep}{pageRep}")

    def console(self, msg, **kwargs):
        """Print something to the output.

        This works exactly as `tf.core.helpers.console`

        When the silent member of the object is True, the message will be suppressed.
        """
        silent = self.silent

        if not silent:
            console(msg, **kwargs)

    def getRotations(self):
        if self.error:
            return

        scanRefDir = self.scanRefDir

        rotateFile = f"{scanRefDir}/rotation_pages.tsv"

        rotateInfo = {}
        self.rotateInfo = rotateInfo

        if not fileExists(rotateFile):
            console(f"Rotation file not found: {rotateFile}")
            return

        with fileOpen(rotateFile) as rh:
            next(rh)
            for line in rh:
                fields = line.rstrip("\n").split("\t")
                p = fields[0]
                rot = int(fields[1])
                rotateInfo[p] = rot

    def getSizes(self):
        if self.error:
            return

        scanRefDir = self.scanRefDir
        doCovers = self.doCovers
        silent = self.silent

        self.sizeInfo = getImageSizes(scanRefDir, doCovers, silent) or {}

    def getPageSeq(self):
        if self.error:
            return

        manifestLevel = self.manifestLevel
        doCovers = self.doCovers
        zoneBased = self.settings.get("zoneBased", False)

        if doCovers:
            coversDir = self.coversDir
            covers = sorted(
                stripExt(f) for f in dirContents(coversDir)[0] if f is not DS_STORE
            )
            self.covers = covers

        pageInfoDir = self.pageInfoDir

        pages = getPageInfo(pageInfoDir, zoneBased, manifestLevel)

        if doCovers:
            pages["covers"] = covers

        self.pages = pages

    def genPages(self, kind, folder=None, file=None):
        if self.error:
            return (0, 0)

        prod = self.prod
        settings = self.settings
        scanRefDir = self.scanRefDir
        ext = settings.get("constants", {}).get("ext", "jpg")
        missingFiles = self.missingFiles

        manifestLevel = self.manifestLevel
        zoneBased = settings.get("zoneBased", False)

        templates = self.templates
        sizeInfo = self.sizeInfo.get(kind, {})
        rotateInfo = None if kind == "covers" else self.rotateInfo
        things = self.pages[kind]
        theseThings = things if folder is None else things.get(folder, None)

        if manifestLevel == "folder":
            thesePages = theseThings or []
        else:
            thesePages = (
                theseThings if file is None else (theseThings or {}).get(file, [])
            )

        if kind == "covers":
            folder = "covers"

        pageItem = templates.coverItem if kind == "covers" else templates.pageItem

        itemsSeen = set()

        items = []

        nPages = 0

        for p in thesePages:
            nPages += 1

            if zoneBased:
                if type(p) is str:
                    (p, region) = (p, "full")
                elif len(p) == 0:
                    (p, region) = ("NA", "full")
                elif len(p) == 1:
                    (p, region) = (p[0], "full")
                else:
                    (p, region) = p[0:2]
            else:
                region = "full"

            if prod == "preview":
                scanPresent = p in sizeInfo
            else:
                pFile = f"{scanRefDir}/{kind}/{p}.{ext}"
                scanPresent = fileExists(pFile)

            if scanPresent:
                w, h = sizeInfo.get(p, (0, 0))
                rot = 0 if rotateInfo is None else rotateInfo.get(p, 0)
            else:
                missingFiles.setdefault(kind, {}).setdefault(
                    file, collections.Counter()
                )[p] += 1
                p = FILE_NOT_FOUND
                w, h = FILE_NOT_FOUND_SIZES
                rot = 0

            key = (p, w, h, rot)

            if key in itemsSeen:
                continue

            itemsSeen.add(key)

            if not scanPresent:
                myDir = self.myDir
                fof = f"{FILE_NOT_FOUND}.{ext}"
                fofInPath = f"{myDir}/fof/{fof}"
                fofOutDir = f"{scanRefDir}/{kind}"
                fofOutPath = f"{fofOutDir}/{fof}"

                if not fileExists(fofOutPath):
                    dirMake(fofOutDir)
                    fileCopy(fofInPath, fofOutPath)

            item = {}

            for k, v in pageItem.items():
                v = fillinIIIF(
                    v,
                    folder=folder,
                    file=file,
                    page=p,
                    region=region,
                    width=w,
                    height=h,
                    rot=rot,
                )
                item[k] = v

            items.append(item)

        pageSequence = (
            templates.coverSequence if kind == "covers" else templates.pageSequence
        )
        manifestDir = self.manifestDir

        data = {}

        for k, v in pageSequence.items():
            v = fillinIIIF(v, folder=folder, file=file)
            data[k] = v

        data["items"] = items

        nItems = len(items)

        if nItems:
            writeJson(
                data,
                asFile=(
                    f"{manifestDir}/{folder}.json"
                    if manifestLevel == "folder"
                    else f"{manifestDir}/{folder}/{file}.json"
                ),
            )
        return (nPages, nItems)

    def manifests(self):
        if self.error:
            return

        # silent = self.silent
        mirador = self.mirador
        folders = self.folders
        manifestDir = self.manifestDir
        logoInDir = self.logoInDir
        logoDir = self.logoDir
        doCovers = self.doCovers
        manifestLevel = self.manifestLevel
        pageInfoDir = self.pageInfoDir

        prod = self.prod
        settings = self.settings
        server = settings["switches"][prod]["server"]

        initTree(manifestDir, fresh=True)

        miradorHtmlIn = self.miradorHtmlIn
        miradorHtmlOut = self.miradorHtmlOut

        with fileOpen(miradorHtmlIn) as fh:
            miradorHtml = fh.read()

        miradorHtml = miradorHtml.replace("«manifests»", mirador.manifests)
        miradorHtml = miradorHtml.replace("«example»", mirador.example)

        with fileOpen(miradorHtmlOut, "w") as fh:
            fh.write(miradorHtml)

        missingFiles = {}
        self.missingFiles = missingFiles

        if doCovers:
            coversHtmlIn = self.coversHtmlIn
            coversHtmlOut = self.coversHtmlOut

            with fileOpen(coversHtmlIn) as fh:
                coversHtml = fh.read()

            coversHtml = coversHtml.replace("«server»", server)

            with fileOpen(coversHtmlOut, "w") as fh:
                fh.write(coversHtml)

            self.genPages("covers")

        p = 0
        i = 0
        m = 0

        if manifestLevel == "folder":
            for folder in folders:
                (thisP, thisI) = self.genPages("pages", folder=folder)
                p += thisP
                i += thisI

                if thisI:
                    m += 1
        else:
            for folder, files in folders:
                folderDir = f"{manifestDir}/{folder}"
                initTree(folderDir, fresh=True, gentle=False)

                folderI = 0

                for file in files:
                    (thisP, thisI) = self.genPages("pages", folder=folder, file=file)
                    p += thisP
                    i += thisI

                    if thisI:
                        m += 1

                    folderI += thisI

                if folderI == 0:
                    dirRemove(folderDir)

        if dirExists(logoInDir):
            dirCopy(logoInDir, logoDir)
        else:
            console(f"Directory with logos not found: {logoInDir}", error=True)

        if len(missingFiles):
            console("Missing image files:", error=True)

        with fileOpen(f"{pageInfoDir}/facsMissing.tsv", "w") as fh:
            fh.write("kind\tfile\tpage\tn\n")
            nMissing = 0

            for kind, files in missingFiles.items():
                console(f"\t{kind}:", error=True)

                for file, pages in files.items():
                    console(f"\t\t{file}:", error=True)

                    for page, n in pages.items():
                        console(f"\t\t\t{n:>3} x {page}", error=True)
                        nMissing += n

                        fh.write(f"{kind}\t{file}\t{page}\t{n}\n")

            console(f"\ttotal occurrences of a missing file: {nMissing}")

        self.console(
            f"{m} IIIF manifests with {i} items for {p} pages generated in {manifestDir}"
        )
