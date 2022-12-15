class WrongNumberColumns(Exception):
    pass


class MessageNotSent(WrongNumberColumns):
    pass


class FailedToRead(WrongNumberColumns):
    pass
