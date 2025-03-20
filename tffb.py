import sys
import os
import re

from shutil import rmtree
from subprocess import run

from tf.tools.pdocs import console, pdoc3serve, pdoc3, servePdocs, shipDocs

ORG = "annotation"
REPO = "text-fabric-factory"
PKG = "tff"
PACKAGE = "text-fabric-factory"
SCRIPT = "/Library/Frameworks/Python.framework/Versions/Current/bin/{PACKAGE}"

DIST = "dist"

TESTPYPI_URL = "https://test.pypi.org/simple/"

VERSION_CONFIG = dict(
    setup=dict(
        file="setup.cfg",
        re=re.compile(r"""version\s*=\s*(\S+)"""),
        mask="version = {}",
    ),
    parameters=dict(
        file="tff/parameters.py",
        re=re.compile(r"""\bVERSION\s*=\s*['"]([^'"]*)['"]"""),
        mask="VERSION = '{}'",
    ),
)

AN_BASE = os.path.expanduser(f"~/github/{ORG}")
TFF_BASE = f"{AN_BASE}/{REPO}"

currentVersion = None
newVersion = None

HELP = """
python tffb.py command

command:

-h
--help


docs  : serve docs locally
pdocs : build docs
pdocsv: serve the built pdocs
sdocs : ship docs
clean : clean local develop build
db    : local develop build
i     : install local non-develop build
ti    : install from testpypi (uninstall first)
g     : push to github, code and docs
pb    : local non-develop build
v     : show current version
r1    : version becomes r1+1.0.0
r2    : version becomes r1.r2+1.0
r3    : version becomes r1.r2.r3+1
ship  : build and ship as a release to pypi
shipt : build and ship as a release to test-pypi
shipb : as shipt, but without docs generation and committing and tagging
shipo : ship to pypi, skip build and commit and tag (after having done a shipt)

For g, ship, shipt you need to pass a commit message.
"""


def readArgs():
    args = sys.argv[1:]
    if not len(args) or args[0] in {"-h", "--help", "help"}:
        console(HELP)
        return (False, None, [])
    arg = args[0]
    if arg not in {
        "docs",
        "pdocs",
        "pdocsv",
        "sdocs",
        "clean",
        "db",
        "i",
        "ti",
        "g",
        "pb",
        "ship",
        "shipt",
        "shipb",
        "shipo",
        "v",
        "r1",
        "r2",
        "r3",
    }:
        console(HELP)
        return (False, None, [])
    if arg in {"g", "ship", "shipt"}:
        if len(args) < 2:
            console("Provide a commit message")
            return (False, None, [])
        return (arg, args[1], args[2:])
    return (arg, None, [])


def incVersion(version, task):
    comps = [int(c) for c in version.split(".")]
    (major, minor, update) = comps
    if task == "r1":
        major += 1
        minor = 0
        update = 0
    elif task == "r2":
        minor += 1
        update = 0
    elif task == "r3":
        update += 1
    return ".".join(str(c) for c in (major, minor, update))


def replaceVersion(task, mask):
    def subVersion(match):
        global currentVersion
        global newVersion
        currentVersion = match.group(1)
        newVersion = incVersion(currentVersion, task)
        return mask.format(newVersion)

    return subVersion


def showVersion():
    global currentVersion
    versions = set()
    for key, c in VERSION_CONFIG.items():
        with open(c["file"]) as fh:
            text = fh.read()
        match = c["re"].search(text)
        version = match.group(1)
        console(f'{version} (according to {c["file"]})')
        versions.add(version)
    currentVersion = None
    if len(versions) == 1:
        currentVersion = list(versions)[0]


def adjustVersion(task):
    for key, c in VERSION_CONFIG.items():
        console(f'Adjusting version in {c["file"]}')
        with open(c["file"]) as fh:
            text = fh.read()
        text = c["re"].sub(replaceVersion(task, c["mask"]), text)
        with open(c["file"], "w") as fh:
            fh.write(text)
    if currentVersion == newVersion:
        console(f"Rebuilding version {newVersion}")
    else:
        console(f"Replacing version {currentVersion} by {newVersion}")


def makeDist(pypi=True, test=False):
    distFile = "{}-{}".format(PACKAGE, currentVersion)
    distFileCompressed = f"{distFile}.tar.gz"
    distPath = f"{DIST}/{distFileCompressed}"
    distPath = f"{DIST}/*"
    if os.path.exists(DIST):
        rmtree(DIST)
    os.makedirs(DIST, exist_ok=True)
    # run(["python", "setup.py", "sdist", "bdist_wheel"])
    # run(["python", "setup.py", "bdist_wheel"])
    run(["python", "-m", "build"])
    if pypi:
        if test:
            run(["twine", "upload", "-r", "testpypi", distPath])
        else:
            run(["twine", "upload", distPath])
        # run("./purge.sh", shell=True)


def commit(task, msg):
    run(["git", "add", "--all", "."])
    run(["git", "commit", "-m", msg])
    run(["git", "push", "origin", "master"])
    if task in {"ship", "shipt"}:
        tagVersion = f"v{currentVersion}"
        commitMessage = f"Release {currentVersion}: {msg}"
        run(["git", "tag", "-a", tagVersion, "-m", commitMessage])
        run(["git", "push", "origin", "--tags"])


def clean():
    # run(["python", "setup.py", "develop", "-u"])
    if os.path.exists(SCRIPT):
        os.unlink(SCRIPT)
    run(["pip", "uninstall", "-y", PACKAGE])


def main():
    (task, msg, remaining) = readArgs()
    if not task:
        return
    elif task == "docs":
        pdoc3serve(PKG)
    elif task == "pdocs":
        pdoc3(PKG)
    elif task == "pdocsv":
        servePdocs(PKG)
    elif task == "sdocs":
        shipDocs(ORG, REPO, PKG)
    elif task == "clean":
        clean()
    elif task == "db":
        clean()
        run("pip install -e .", shell=True)
    elif task == "pb":
        clean()
        makeDist(pypi=False)
    elif task == "i":
        run(
            [
                "pip",
                "install",
                "--upgrade",
                "--no-index",
                "--find-links",
                f"file://{TFF_BASE}/dist",
                PACKAGE,
            ]
        )
    elif task == "ti":
        clean()
        run(
            f"pip install --index-url {TESTPYPI_URL} --no-deps text-fabric-factory",
            shell=True,
        )
    elif task == "g":
        shipDocs(ORG, REPO, PKG)
        commit(task, msg)
    elif task == "v":
        showVersion()
    elif task in {"r", "r1", "r2", "r3"}:
        adjustVersion(task)
    elif task in {"ship", "shipb", "shipt", "shipo"}:
        showVersion()
        if not currentVersion:
            console("No current version")
            return

        answer = input("right version ? [yn]")
        if answer != "y":
            return
        if task not in {"shipb", "shipo"}:
            shipDocs(ORG, REPO, PKG)

        makeDist(test=task in {"shipt", "shipb"})

        if task not in {"shipb", "shipo"}:
            commit(task, msg)


main()
