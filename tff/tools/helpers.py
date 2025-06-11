from subprocess import run as run_cmd, CalledProcessError


def runx(cmdline, workDir=None):
    """Runs a shell command and returns all relevant info.

    The function runs a command-line in a shell, and returns
    whether the command was successful, and also what the output was, separately for
    standard error and standard output.

    Parameters
    ----------
    cmdline: string
        The command-line to execute.
    workDir: string, optional None
        The working directory where the command should be executed.
        If `None` the current directory is used.
    """
    try:
        result = run_cmd(
            cmdline,
            shell=False,
            cwd=workDir,
            check=True,
            capture_output=True,
        )
        stdOut = result.stdout.decode("utf8").strip()
        stdErr = result.stderr.decode("utf8").strip()
        returnCode = 0
        good = True

    except CalledProcessError as e:
        stdOut = e.stdout.decode("utf8").strip()
        stdErr = e.stderr.decode("utf8").strip()
        returnCode = e.returncode
        good = False

    return (good, returnCode, stdOut, stdErr)
