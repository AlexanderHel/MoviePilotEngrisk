from typing import Optional

from app.chain import ChainBase


class UserChain(ChainBase):

    def user_authenticate(self, name, password) -> Optional[str]:
        """
        Assisted completion of user authentication
        :param name:  User id
        :param password:  Cryptographic
        :return: token
        """
        return self.run_module("user_authenticate", name=name, password=password)
