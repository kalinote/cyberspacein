class WikiError(Exception):
    code: int = 241000
    message: str = "Wiki 操作失败"

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class WikiPageNotFoundError(WikiError):
    code = 241001


class WikiSectionNotFoundError(WikiError):
    code = 241002


class WikiRevisionConflictError(WikiError):
    code = 241003


class WikiSlugConflictError(WikiError):
    code = 241004


class WikiCannotDeleteMainError(WikiError):
    code = 241005


class WikiRevisionNotFoundError(WikiError):
    code = 241006


class WikiSnapshotFailedError(WikiError):
    code = 241007
