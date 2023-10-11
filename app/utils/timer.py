import random
from typing import List
import datetime


class TimerUtils:

    @staticmethod
    def random_scheduler(num_executions: int = 1,
                         begin_hour: int = 7,
                         end_hour: int = 23,
                         min_interval: int = 20,
                         max_interval: int = 40) -> List[datetime.datetime]:
        """
        Generate random timers by number of executions
        :param num_executions:  Number of executions
        :param begin_hour:  Starting time
        :param end_hour:  End time
        :param min_interval:  Minimum interval minutes
        :param max_interval:  Maximum interval minutes
        """
        trigger: list = []
        #  Current time
        now = datetime.datetime.now()
        #  Creating randomized time triggers
        random_trigger = now.replace(hour=begin_hour, minute=0, second=0, microsecond=0)
        for _ in range(num_executions):
            #  Randomize the time interval for generating the next task
            interval_minutes = random.randint(min_interval, max_interval)
            random_interval = datetime.timedelta(minutes=interval_minutes)
            #  Time trigger to update the current time to the next task
            random_trigger += random_interval
            #  Exit when end time is reached
            if random_trigger.hour > end_hour:
                break
            #  Add to queue
            trigger.append(random_trigger)

        return trigger

    @staticmethod
    def time_difference(input_datetime: datetime) -> str:
        """
        Determine the time difference between the input time and the current time， Returns the time difference if the input time is greater than the current time， Otherwise returns the empty string
        """
        if not input_datetime:
            return ""
        current_datetime = datetime.datetime.now(datetime.timezone.utc).astimezone()
        time_difference = input_datetime - current_datetime

        if time_difference.total_seconds() < 0:
            return ""

        days = time_difference.days
        hours, remainder = divmod(time_difference.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        time_difference_string = ""
        if days > 0:
            time_difference_string += f"{days} Sky"
        if hours > 0:
            time_difference_string += f"{hours} Hourly"
        if minutes > 0:
            time_difference_string += f"{minutes} Minutes"

        return time_difference_string

    @staticmethod
    def diff_minutes(input_datetime: datetime) -> int:
        """
        Calculate the minute difference between the current time and the entered time
        """
        if not input_datetime:
            return 0
        time_difference = datetime.datetime.now() - input_datetime
        return int(time_difference.total_seconds() / 60)
