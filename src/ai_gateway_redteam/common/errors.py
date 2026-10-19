class RedteamError(Exception):
    """Base for every error this tool raises on purpose."""


class CaseFileError(RedteamError):
    """The case files can't be turned into runnable cases."""


class NoCaseFilesError(CaseFileError):
    """The given path contains no .yaml or .yml files."""


class InvalidCaseError(CaseFileError):
    """A file or a case in it doesn't match the schema, or names an unknown transform."""


class DuplicateCaseIdError(CaseFileError):
    """Two cases share an ID after expansion."""