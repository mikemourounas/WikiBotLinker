import praw
import redis
import requests
import json
import os
import time
from parse import *


# get env variables from dockerfile

r_host = os.environ['REDIS_HOST']
r_port = os.environ['REDIS_PORT']
r_db = os.environ['REDIS_DB']


# initialise reddit object using 'bot1' as defined in praw.ini
try:
    reddit = praw.Reddit('bot1')
except Exception as e:
    print('Reddit Error: ', e)
    sys.exit(1)

# initialise redis
try:
    db = redis.Redis(host=r_host, port=r_port, db=r_db)
except Exception as e:
    print('Redis Error: ', e)
    sys.exit(1)

# define global spam counter to prevent spamming Reddit
spam_count = 0


def check_comment_for_call(comment):
    '''
    function to parse comment text for
    keyword(s) contained within specified
    formatting [[ ]]
    if comment contains keyword(s), return
    keyword(s), else, return None
    '''
    keyword = search('[[{}]]', comment.body)
    print(keyword)

    # check database for comment id,
    # exit if exists (already been processed)
    if db.get(str(comment)) != None:
        print('Already in database: ', comment)
        return None

    # find and return keyword(s)
    elif keyword:
        try:
            search_word = str(keyword[0])
            print('Search word function successful!')
            print(search_word)
            return search_word
        except SyntaxError as e:
            print(SyntaxError)
            return None
        except UnicodeError as e:
            print(UnicodeError)
            return None
        except Exception as e:
            print('Other Keyword Error: ', e)
            return None


def get_wiki_link(search_word):
    '''
    function to contact wiki api's opensearch
    and return the title and link of the
    top result
    '''
    wiki_search = requests.get(
        'https://en.wikipedia.org/w/api.php?action=opensearch&format=json&search=' + search_word)

    # check statuscode
    sc = wiki_search.status_code
    if str(sc)[0] == '4':
        print('Opensearch Error (400): ', sc)
        time.sleep(5)
        get_wiki_link(search_word)
    elif str(sc)[0] == '5':
        print('Opensearch Error (500): ', sc)
        return None
    elif sc == 200:
        wiki_cont = wiki_search.content
        wiki_list = json.loads(wiki_cont)
        try:
            top_wiki_title = wiki_list[1][0]
            top_wiki_link = wiki_list[3][0]
        except IndexError as e:
            print('Index Error: ', e)
            return None
        except Exception as e:
            print('Other List Error: ', e)
            return None

        return [top_wiki_title, top_wiki_link]
    else:
        print('Other Opensearch Error')
        return None


def comment_with_wiki_link(top_wiki_title, top_wiki_link):
    '''
    function to respond to relevant comment
    with reply containing hyperlink to
    top wiki search result
    '''
    try:
        comment.reply('['+top_wiki_title+']('+top_wiki_link+')')
        db.set(str(comment), search_word)
        print('Successfully replied to ', comment.id)
        return 1
    except praw.exceptions.APIException:  # kill if PRAW spam filters
        print('PRAW spam exception: try again in ten minutes')
        sys.exit(1)
    except Exception as e:
        print('Reply Error: ', e)
        return 0


'''
# define subreddit name
# set to r/test for now, when put into ECS 
this will be defined by a message from an sqs queue
'''
subreddit_name = 'test'

try:
    subreddit = reddit.subreddit(subreddit_name)
except Exception as e:
    print('Subreddit Error: ', e)
    sys.exit(1)

# search comment stream for bracketed formatting
for comment in subreddit.stream.comments():
    print('Running main loop...')
    search_word = check_comment_for_call(comment)
    print(search_word)
    # if search_word exists, execute wiki Opensearch and return
    if search_word:
        print('Search word found...')
        wiki_info = get_wiki_link(search_word)
        if wiki_info:
            print('Wiki info returned...')
            time.sleep(10)
            top_wiki_title = wiki_info[0]
            top_wiki_link = wiki_info[1]
            print(top_wiki_title)
            print(top_wiki_link)
            comment_with_wiki_link(top_wiki_title, top_wiki_link)
