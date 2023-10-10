import json
import time
from typing import List, Union

import openai
from cacheout import Cache

OpenAISessionCache = Cache(maxsize=100, ttl=3600, timer=time.time, default=None)


class OpenAi:
    _api_key: str = None
    _api_url: str = None

    def __init__(self, api_key: str = None, api_url: str = None, proxy: dict = None):
        self._api_key = api_key
        self._api_url = api_url
        openai.api_base = self._api_url + "/v1"
        openai.api_key = self._api_key
        if proxy and proxy.get("https"):
            openai.proxy = proxy.get("https")

    def get_state(self) -> bool:
        return True if self._api_key else False

    @staticmethod
    def __save_session(session_id: str, message: str):
        """
        Save session
        :param session_id:  ConversationsID
        :param message:  Messages
        :return:
        """
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({
                "role": "assistant",
                "content": message
            })
            OpenAISessionCache.set(session_id, seasion)

    @staticmethod
    def __get_session(session_id: str, message: str) -> List[dict]:
        """
        Get session
        :param session_id:  ConversationsID
        :return:  Session context
        """
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({
                "role": "user",
                "content": message
            })
        else:
            seasion = [
                {
                    "role": "system",
                    "content": " Please reply in chinese for the rest of the conversation.， And as detailed as possible。"
                },
                {
                    "role": "user",
                    "content": message
                }]
            OpenAISessionCache.set(session_id, seasion)
        return seasion

    @staticmethod
    def __get_model(message: Union[str, List[dict]],
                    prompt: str = None,
                    user: str = "MoviePilot",
                    **kwargs):
        """
        Getting the model
        """
        if not isinstance(message, list):
            if prompt:
                message = [
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            else:
                message = [
                    {
                        "role": "user",
                        "content": message
                    }
                ]
        return openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            user=user,
            messages=message,
            **kwargs
        )

    @staticmethod
    def __clear_session(session_id: str):
        """
        Clearing a session
        :param session_id:  ConversationsID
        :return:
        """
        if OpenAISessionCache.get(session_id):
            OpenAISessionCache.delete(session_id)

    def get_media_name(self, filename: str):
        """
        Extract elements such as media names from file names
        :param filename:  Filename
        :return: Json
        """
        if not self.get_state():
            return None
        result = ""
        try:
            _filename_prompt = "I will give you a movie/tvshow file name.You need to return a Json." \
                               "\nPay attention to the correct identification of the film name." \
                               "\n{\"title\":string,\"version\":string,\"part\":string,\"year\":string,\"resolution\":string,\"season\":number|null,\"episode\":number|null}"
            completion = self.__get_model(prompt=_filename_prompt, message=filename)
            result = completion.choices[0].message.content
            return json.loads(result)
        except Exception as e:
            print(f"{str(e)}：{result}")
            return {}

    def get_response(self, text: str, userid: str):
        """
        Chat， Get answers
        :param text:  Input text
        :param userid:  SubscribersID
        :return:
        """
        if not self.get_state():
            return ""
        try:
            if not userid:
                return " User information error"
            else:
                userid = str(userid)
            if text == "# Removals":
                self.__clear_session(userid)
                return " Session cleared"
            #  Getting historical context
            messages = self.__get_session(userid, text)
            completion = self.__get_model(message=messages, user=userid)
            result = completion.choices[0].message.content
            if result:
                self.__save_session(userid, text)
            return result
        except openai.error.RateLimitError as e:
            return f" Requested byChatGPT Rejected.，{str(e)}"
        except openai.error.APIConnectionError as e:
            return f"ChatGPT Network connection failure：{str(e)}"
        except openai.error.Timeout as e:
            return f" No reception.ChatGPT Return message of the：{str(e)}"
        except Exception as e:
            return f" RequestingChatGPT Error：{str(e)}"

    def translate_to_zh(self, text: str):
        """
        Translation into chinese
        :param text:  Input text
        """
        if not self.get_state():
            return False, None
        system_prompt = "You are a translation engine that can only translate text and cannot interpret it."
        user_prompt = f"translate to zh-CN:\n\n{text}"
        result = ""
        try:
            completion = self.__get_model(prompt=system_prompt,
                                          message=user_prompt,
                                          temperature=0,
                                          top_p=1,
                                          frequency_penalty=0,
                                          presence_penalty=0)
            result = completion.choices[0].message.content.strip()
            return True, result
        except Exception as e:
            print(f"{str(e)}：{result}")
            return False, str(e)

    def get_question_answer(self, question: str):
        """
        Getting the right answer from the given question and options
        :param question:  Questions and options
        :return: Json
        """
        if not self.get_state():
            return None
        result = ""
        try:
            _question_prompt = " Let's play a game.， You're a teacher.， I'm a student.， You need to answer my questions.， I'll give you a question and a few options.， Your response must be the serial number corresponding to the correct answer in the given options， Please reply directly to the number"
            completion = self.__get_model(prompt=_question_prompt, message=question)
            result = completion.choices[0].message.content
            return result
        except Exception as e:
            print(f"{str(e)}：{result}")
            return {}
