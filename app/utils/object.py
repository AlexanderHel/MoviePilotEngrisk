import inspect
from types import FunctionType
from typing import Any, Callable


class ObjectUtils:

    @staticmethod
    def is_obj(obj: Any):
        if isinstance(obj, list) \
                or isinstance(obj, dict) \
                or isinstance(obj, tuple):
            return True
        elif isinstance(obj, int) \
                or isinstance(obj, float) \
                or isinstance(obj, bool) \
                or isinstance(obj, bytes):
            return False
        else:
            return str(obj).startswith("{") \
                or str(obj).startswith("[")

    @staticmethod
    def arguments(func: Callable) -> int:
        """
        Returns the number of arguments to the function
        """
        signature = inspect.signature(func)
        parameters = signature.parameters

        return len(list(parameters.keys()))

    @staticmethod
    def check_method(func: FunctionType) -> bool:
        """
        Check if the function has been implemented
        """
        return func.__code__.co_code not in [b'd\x01S\x00', b'\x97\x00d\x00S\x00']

    @staticmethod
    def check_signature(func: FunctionType, *args) -> bool:
        """
        Check that the output matches the type of the function's arguments
        """
        #  Getting information about a function's arguments
        signature = inspect.signature(func)
        parameters = signature.parameters

        #  Check the number and type of input parameters for consistency
        if len(args) != len(parameters):
            return False
        for arg, param in zip(args, parameters.values()):
            if not isinstance(arg, param.annotation):
                return False
        return True
