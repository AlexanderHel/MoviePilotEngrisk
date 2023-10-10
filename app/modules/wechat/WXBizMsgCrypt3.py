#!/usr/bin/env python
# -*- encoding:utf-8 -*-

"""  Sample code for encrypting and decrypting messages sent by enterprise wechat to the enterprise backend.
@copyright: Copyright (c) 1998-2014 Tencent Inc.

"""
import base64
import hashlib
# ------------------------------------------------------------------------
import logging
import random
import socket
import struct
import time
import xml.etree.cElementTree as ET

from Crypto.Cipher import AES

# Description: Define the meaning of the error code
#########################################################################
WXBizMsgCrypt_OK = 0
WXBizMsgCrypt_ValidateSignature_Error = -40001
WXBizMsgCrypt_ParseXml_Error = -40002
WXBizMsgCrypt_ComputeSignature_Error = -40003
WXBizMsgCrypt_IllegalAesKey = -40004
WXBizMsgCrypt_ValidateCorpid_Error = -40005
WXBizMsgCrypt_EncryptAES_Error = -40006
WXBizMsgCrypt_DecryptAES_Error = -40007
WXBizMsgCrypt_IllegalBuffer = -40008
WXBizMsgCrypt_EncodeBase64_Error = -40009
WXBizMsgCrypt_DecodeBase64_Error = -40010
WXBizMsgCrypt_GenReturnXml_Error = -40011

"""
Crypto.Cipher With respect to，ImportError: No module named 'Crypto' Module (in software)
 Prescription
https://www.dlitz.net/software/pycrypto/  Please go to the official websitepycrypto。
 Downloading
， After downloadingREADME On the basis of“Installation” Hit the nail on the headpycrypto The prompts in the vignettes carry。
 Mounting
"""


class FormatException(Exception):
    pass


def throw_exception(message, exception_class=FormatException):
    """my define raise exception function"""
    raise exception_class(message)


class SHA1:
    """ Calculating the message signature interface for enterprise wechat"""

    @staticmethod
    def getSHA1(token, timestamp, nonce, encrypt):
        """ Expense or outlaySHA1 Algorithmic generation of secure signatures
        @param token:   Bill
        @param timestamp:  Timestamp
        @param encrypt:  Coded text
        @param nonce:  Random string
        @return:  Secure signature
        """
        try:
            sortlist = [token, timestamp, nonce, encrypt]
            sortlist.sort()
            sha = hashlib.sha1()
            sha.update("".join(sortlist).encode())
            return WXBizMsgCrypt_OK, sha.hexdigest()
        except Exception as e:
            logger = logging.getLogger()
            logger.error(e)
            return WXBizMsgCrypt_ComputeSignature_Error, None


class XMLParse:
    """ Provide interfaces for extracting ciphertext from message formats and generating reply message formats."""

    # xml Message templates
    AES_TEXT_RESPONSE_TEMPLATE = """<xml>
<Encrypt><![CDATA[%(msg_encrypt)s]]></Encrypt>
<MsgSignature><![CDATA[%(msg_signaturet)s]]></MsgSignature>
<TimeStamp>%(timestamp)s</TimeStamp>
<Nonce><![CDATA[%(nonce)s]]></Nonce>
</xml>"""

    @staticmethod
    def extract(xmltext):
        """ Extractxml Encrypted messages in packets
        @param xmltext:  Prospectivexml String (computer science)
        @return:  Extracted encrypted message string
        """
        try:
            xml_tree = ET.fromstring(xmltext)
            encrypt = xml_tree.find("Encrypt")
            return WXBizMsgCrypt_OK, encrypt.text
        except Exception as e:
            logger = logging.getLogger()
            logger.error(e)
            return WXBizMsgCrypt_ParseXml_Error, None

    def generate(self, encrypt, signature, timestamp, nonce):
        """ Generatingxml Messages
        @param encrypt:  Encrypted message cipher
        @param signature:  Secure signature
        @param timestamp:  Timestamp
        @param nonce:  Random string
        @return:  Generatedxml String (computer science)
        """
        resp_dict = {
            'msg_encrypt': encrypt,
            'msg_signaturet': signature,
            'timestamp': timestamp,
            'nonce': nonce,
        }
        resp_xml = self.AES_TEXT_RESPONSE_TEMPLATE % resp_dict
        return resp_xml


class PKCS7Encoder:
    """ ProvidePKCS7 Encryption and decryption interfaces for algorithms"""

    block_size = 32

    def encode(self, text):
        """  Padding complement for plaintext to be encrypted
        @param text:  Plaintexts that require a fill-fill operation
        @return:  Complementary plaintext strings
        """
        text_length = len(text)
        #  Calculate the number of bits to be filled
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        #  Get the character used for the complement
        pad = chr(amount_to_pad)
        return text + (pad * amount_to_pad).encode()

    @staticmethod
    def decode(decrypted):
        """ Deletes the complementary characters of the decrypted plaintext.
        @param decrypted:  Decrypted plaintext
        @return:  Plaintext after deletion of the complementary character
        """
        pad = ord(decrypted[-1])
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad]


class Prpcrypt(object):
    """ Provide encryption and decryption interfaces for receiving and pushing wechat messages to enterprises"""

    def __init__(self, key):

        # self.key = base64.b64decode(key+"=")
        self.key = key
        #  Set the encryption and decryption mode toAES (used form a nominal expression)CBC Paradigm
        self.mode = AES.MODE_CBC

    def encrypt(self, text, receiveid):
        """ Encrypting plaintext
        @param text:  Plaintext (computing) that requires encryption
        @param receiveid: receiveid
        @return:  Encrypted string
        """
        # 16 Bit random string added to the beginning of the plaintext
        text = text.encode()
        text = self.get_random_str() + struct.pack("I", socket.htonl(len(text))) + text + receiveid.encode()

        #  Complementary padding of plaintexts using customized padding methods
        pkcs7 = PKCS7Encoder()
        text = pkcs7.encode(text)
        #  Encrypted
        cryptor = AES.new(self.key, self.mode, self.key[:16])
        try:
            ciphertext = cryptor.encrypt(text)
            #  UtilizationBASE64 Encoding the encrypted string
            return WXBizMsgCrypt_OK, base64.b64encode(ciphertext)
        except Exception as e:
            logger = logging.getLogger()
            logger.error(e)
            return WXBizMsgCrypt_EncryptAES_Error, None

    def decrypt(self, text, receiveid):
        """ Complementary deletion of the decrypted plaintext
        @param text:  Coded text
        @param receiveid: receiveid
        @return:  Delete plaintext after padding complement
        """
        try:
            cryptor = AES.new(self.key, self.mode, self.key[:16])
            #  UtilizationBASE64 Decode the ciphertext， After thatAES-CBC Declassification
            plain_text = cryptor.decrypt(base64.b64decode(text))
        except Exception as e:
            logger = logging.getLogger()
            logger.error(e)
            return WXBizMsgCrypt_DecryptAES_Error, None
        try:
            pad = plain_text[-1]
            #  Remove complementary strings
            # pkcs7 = PKCS7Encoder()
            # plain_text = pkcs7.encode(plain_text)
            #  Dislodge16 Bitwise random string
            content = plain_text[16:-pad]
            xml_len = socket.ntohl(struct.unpack("I", content[: 4])[0])
            xml_content = content[4: xml_len + 4]
            from_receiveid = content[xml_len + 4:]
        except Exception as e:
            logger = logging.getLogger()
            logger.error(e)
            return WXBizMsgCrypt_IllegalBuffer, None

        if from_receiveid.decode('utf8') != receiveid:
            return WXBizMsgCrypt_ValidateCorpid_Error, None
        return 0, xml_content

    @staticmethod
    def get_random_str():
        """  Randomly generated16 Bit string
        @return: 16 Bit string
        """
        return str(random.randint(1000000000000000, 9999999999999999)).encode()


class WXBizMsgCrypt(object):
    #  Constructor
    def __init__(self, sToken, sEncodingAESKey, sReceiveId):
        try:
            self.key = base64.b64decode(sEncodingAESKey + "=")
            assert len(self.key) == 32
        except Exception as err:
            print(str(err))
            throw_exception("[error]: EncodingAESKey unvalid !", FormatException)
            # return WXBizMsgCrypt_IllegalAesKey,None
        self.m_sToken = sToken
        self.m_sReceiveId = sReceiveId

        #  Validate (a theory)URL
        # @param sMsgSignature:  Signature string， HomologousURL Parametricmsg_signature
        # @param sTimeStamp:  Timestamp， HomologousURL Parametrictimestamp
        # @param sNonce:  Random string， HomologousURL Parametricnonce
        # @param sEchoStr:  Random string， HomologousURL Parametricechostr
        # @param sReplyEchoStr:  Declassifiedechostr， (coll.) fail (a student)return Come (or go) back0 Currently valid
        # @return： Successes0， Failure returns the corresponding error code

    def VerifyURL(self, sMsgSignature, sTimeStamp, sNonce, sEchoStr):
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.m_sToken, sTimeStamp, sNonce, sEchoStr)
        if ret != 0:
            return ret, None
        if not signature == sMsgSignature:
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = Prpcrypt(self.key)
        ret, sReplyEchoStr = pc.decrypt(sEchoStr, self.m_sReceiveId)
        return ret, sReplyEchoStr

    def EncryptMsg(self, sReplyMsg, sNonce, timestamp=None):
        #  Encrypted packaging of corporate replies to users
        # @param sReplyMsg:  Enterprise pending reply to user's message，xml Formatted strings
        # @param sTimeStamp:  Timestamp， You can generate your own， It is also possible to useURL Parametrictimestamp, IfNone Then the current time is automatically used
        # @param sNonce:  Random string， You can generate your own， It is also possible to useURL Parametricnonce
        # sEncryptMsg:  Encrypted cipher text that can be directly replied to by the user， Including throughmsg_signature, timestamp, nonce, encrypt (used form a nominal expression)xml Formatted strings,
        # return： Successes0，sEncryptMsg, Failure returns the corresponding error codeNone
        pc = Prpcrypt(self.key)
        ret, encrypt = pc.encrypt(sReplyMsg, self.m_sReceiveId)
        encrypt = encrypt.decode('utf8')
        if ret != 0:
            return ret, None
        if timestamp is None:
            timestamp = str(int(time.time()))
        #  Generate secure signatures
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.m_sToken, timestamp, sNonce, encrypt)
        if ret != 0:
            return ret, None
        xmlParse = XMLParse()
        return ret, xmlParse.generate(encrypt, signature, timestamp, sNonce)

    def DecryptMsg(self, sPostData, sMsgSignature, sTimeStamp, sNonce):
        #  Test the authenticity of the message， And get the decrypted plaintext
        # @param sMsgSignature:  Signature string， HomologousURL Parametricmsg_signature
        # @param sTimeStamp:  Timestamp， HomologousURL Parametrictimestamp
        # @param sNonce:  Random string， HomologousURL Parametricnonce
        # @param sPostData:  Coded text， HomologousPOST Requested data
        #  xml_content:  Declassified original， (coll.) fail (a student)return Come (or go) back0 Currently valid
        # @return:  Successes0， Failure returns the corresponding error code
        #  Verify security signatures
        xmlParse = XMLParse()
        ret, encrypt = xmlParse.extract(sPostData)
        if ret != 0:
            return ret, None
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.m_sToken, sTimeStamp, sNonce, encrypt)
        if ret != 0:
            return ret, None
        if not signature == sMsgSignature:
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = Prpcrypt(self.key)
        ret, xml_content = pc.decrypt(encrypt, self.m_sReceiveId)
        return ret, xml_content
