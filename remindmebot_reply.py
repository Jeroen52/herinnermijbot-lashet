#!/usr/bin/env python2.7

# =============================================================================
# IMPORTS
# =============================================================================

import praw
import OAuth2Util
import re
import MySQLdb
import ConfigParser
import time
from datetime import datetime, timedelta
from requests.exceptions import HTTPError, ConnectionError, Timeout
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout
from pytz import timezone

# =============================================================================
# GLOBALS
# =============================================================================

# Reads the config file
config = ConfigParser.ConfigParser()
config.read("remindmebot.cfg")

#Reddit info
reddit = praw.Reddit("RemindMeB0tReply")
o = OAuth2Util.OAuth2Util(reddit, print_log=True)
o.refresh(force=True)
# DB Info
DB_USER = config.get("SQL", "user")
DB_PASS = config.get("SQL", "passwd")

# =============================================================================
# CLASSES
# =============================================================================

class Connect(object):
    """
    DB connection class
    """
    connection = None
    cursor = None

    def __init__(self):
        self.connection = MySQLdb.connect(
            host="localhost", user=DB_USER, passwd=DB_PASS, db="bot"
        )
        self.cursor = self.connection.cursor()

class Reply(object):

    def __init__(self):
        self._queryDB = Connect()
        self._replyMessage =(
            "HerinnerMijBot privé bericht hier!" 
            "\n\n**Het bericht:** \n\n>{message}"
            "\n\n**Het originele commentaar:** \n\n>{original}"
            "\n\n**Het ouderlijke commentaar van het originele commentaar of zijn paal:** \n\n>{parent}"
            "{origin_date_text}"
            "\n\n#Zou je het leuk vinden om het originele commentaar weer te zien? Gewoon je tijd opnieuw zetten na het HerinnerMij! opdracht. [CLICK HERE]"
            "(http://np.reddit.com/message/compose/?to=HerinnerMijBot&subject=Herinner&message=[{original}]"
            "%0A%0AHerinnerMij!)"
            "\n\n_____\n\n"
            "|[^(VGV)](http://np.reddit.com/r/HerinnerMijBot/is/wel/kut/dat/je/dit/leest/want/dit/moet/aangepast/worden/)"
            "|[^(Aanpassen)](http://np.reddit.com/message/compose/?to=HerinnerMijBot&subject=Herinner&message="
                "[SCHAKELTJE BINNEN VIERKANTEN HAAKJES anders standaard op VGVen]%0A%0A"
                "NOTITIE: Niet vergeten om toe te voegen tijd opties na het opdracht.%0A%0AHerinnerMij!)"
            "|[^(Jouw Herinnneringen)](http://np.reddit.com/message/compose/?to=HerinnerMijBot&subject=Lijst Van Herinneringen&message=MijnHerinneringen!)"
            "|[^(Voedterug)](http://np.reddit.com/message/compose/?to=Jeroen52&subject=Voedterug)"
            "|[^(Code)](https://github.com/Jeroen52/herinnermijbot-lashet)"
            "|[^(Browser Extensies)](https://np.reddit.com/r/HerinnerMijBot/moeten/wij/eigenlijk/ook/maken/)"
            "\n|-|-|-|-|-|-|"
            )

    def parent_comment(self, dbPermalink):
        """
        Returns the parent comment or if it's a top comment
        return the original submission
        """
        try:
            commentObj = reddit.get_submission(_force_utf8(dbPermalink)).comments[0]
            if commentObj.is_root:
                return _force_utf8(commentObj.submission.permalink)
            else:
                return _force_utf8(reddit.get_info(thing_id=commentObj.parent_id).permalink)
        except IndexError as err:
            print "vader_commentaar foutmelding"
            return "Het ziet er naar uit jouw originele commentaar verwijdert is, het is niet mogelijk om het ouder commentaar te krijgen."
        # Catch any URLs that are not reddit comments
        except Exception  as err:
            print "HTTPFoutmelding/PRAW Ouder commentaar"
            return "Ouder commentaar niet verplicht voor dit UHZ."

    def time_to_reply(self):
        """
        Checks to see through SQL if net_date is < current time
        """

        # get current time to compare
        currentTime = datetime.now(timezone('UTC'))
        currentTime = format(currentTime, '%Y-%m-%d %H:%M:%S')
        cmd = "SELECT * FROM message_date WHERE new_date < %s"
        self._queryDB.cursor.execute(cmd, [currentTime])

    def search_db(self):
        """
        Loop through data looking for which comments are old
        """

        data = self._queryDB.cursor.fetchall()
        alreadyCommented = []
        for row in data:
            # checks to make sure ID hasn't been commented already
            # For situtations where errors happened
            if row[0] not in alreadyCommented:
                flagDelete = False
                # MySQl- permalink, message, origin date, reddit user
                flagDelete = self.new_reply(row[1],row[2], row[4], row[5])
                # removes row based on flagDelete
                if flagDelete:
                    cmd = "DELETE FROM message_date WHERE id = %s" 
                    self._queryDB.cursor.execute(cmd, [row[0]])
                    self._queryDB.connection.commit()
                    alreadyCommented.append(row[0])

        self._queryDB.connection.commit()
        self._queryDB.connection.close()

    def new_reply(self, permalink, message, origin_date, author):
        """
        Replies a second time to the user after a set amount of time
        """ 
        """
        print self._replyMessage.format(
                message,
                permalink
            )
        """
        print "---------------"
        print author
        print permalink

        origin_date_text = ""
        # Before feature was implemented, there are no origin dates stored
        if origin_date is not None:
            origin_date_text =  ("\n\nJe hebt deze herinnering gevraagt op: " 
                                "[**" + _force_utf8(origin_date) + " UTC**](http://www.wolframalpha.com/input/?i="
                                + _force_utf8(origin_date) + " UTC To Local Time)")

        try:
            reddit.send_message(
                recipient=str(author), 
                subject='Hallo, ' + _force_utf8(str(author)) + ' HerrinnerMijBot Hier!', 
                message=self._replyMessage.format(
                    message=_force_utf8(message),
                    original=_force_utf8(permalink),
                    parent= self.parent_comment(permalink),
                    origin_date_text = origin_date_text
                ))
            print "Gedaan Het"
            return True    
        except InvalidUser as err:
            print "InvalidUser", err
            return True
        except APIException as err:
            print "APIException", err
            return False
        except IndexError as err:
            print "IndexError", err
            return False
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print "HTTPError", err
            time.sleep(10)
            return False
        except RateLimitExceeded as err:
            print "RateLimitExceeded", err
            time.sleep(10)
            return False
        except praw.errors.HTTPException as err:
            print"praw.errors.HTTPException"
            time.sleep(10)
            return False

"""
From Reddit's Code 
https://github.com/reddit/reddit/blob/master/r2/r2/lib/unicode.py
Brought to attention thanks to /u/13steinj
"""
def _force_unicode(text):

    if text == None:
        return u''

    if isinstance(text, unicode):
        return text

    try:
        text = unicode(text, 'utf-8')
    except UnicodeDecodeError:
        text = unicode(text, 'latin1')
    except TypeError:
        text = unicode(text)
    return text


def _force_utf8(text):
    return str(_force_unicode(text).encode('utf8'))


# =============================================================================
# MAIN
# =============================================================================

def main():
    while True:
        checkReply = Reply()
        checkReply.time_to_reply()
        checkReply.search_db()
        time.sleep(10)


# =============================================================================
# RUNNER
# =============================================================================
print "start"
if __name__ == '__main__':
    main()