import argparse
import bz2
import io
import json
import lzma
import os
import re
import requests
import subprocess
import urllib
import zstandard as zstd

from bs4 import BeautifulSoup
from glob import glob
from os.path import isfile
from os.path import join as pjoin
from time import sleep, time

from data_utils import *

REDDIT_URL  = "https://files.pushshift.io/reddit/"

name = "name"

sales = [
"Agreement",
"Deals",
"Sales",
"Package",
"Dollar",
"Euro",
"Aid",
"security support",
"military support",
"Guarantee",
"Loan",
"Delivery",
"Transfer",
"Detterent",
"money"
"consignment",]
weapon = [
"Missile",
"rocket",
"war",
"System",
"Arms",
"Munition",
"Weapon",
"Bomb",
"Warhead",
"Defense",
]

def targeted_text(t):
    # if type(t) != str:
    #     return False
    first = False
    for s in sales:
        #TODO: add plural check
        if s.lower() in t:
            print(s)
            first = True
            break
    if not first:
        return False
    
    for w in weapon:
        if w.lower() in t:
            print(w)
            return True
    return False
        

# collects URLs for monthly dumps, has to be robust to file type changes
def gather_dump_urls(base_url, mode):
    page    = requests.get(base_url + mode)
    soup    = BeautifulSoup(page.content, 'lxml')
    files   = [it for it in soup.find_all(attrs={"class":"file"})]
    f_urls  = [tg.find_all(lambda x:x.has_attr('href'))[0]['href']
               for tg in files if len(tg.find_all(lambda x:x.has_attr('href'))) > 0]
    date_to_url    = {}
    for url_st in f_urls:
        ls  = re.findall(r"20[0-9]{2}-[0-9]{2}", url_st)
        if len(ls) > 0:
            yr, mt  = ls[0].split('-')
            date_to_url[(int(yr), int(mt))] = base_url + mode + url_st[1:]
    return date_to_url


# select valid top-level comments
def valid_comment(a):
    res = len(a['body'].split()) > 2
    # and \
    #       not a['body'].startswith('Your submission has been removed') and \
    #       a['author'] != 'AutoModerator' and a['parent_id'] == a['link_id']
    return res


# download a file, extract posts from desired subreddit, then remove from disk
def download_and_process(file_url, mode, st_time):
    # download and pre-process original posts
    f_name  = pjoin('reddit_tmp', file_url.split('/')[-1])
    tries_left  = 4
    while tries_left:
        try:
            print("downloading %s %2f" % (f_name, time() - st_time))
            subprocess.run(['wget', '-P', 'reddit_tmp', file_url], stdout=subprocess.PIPE)
            print("decompressing and filtering %s %2f" % (f_name, time() - st_time))
            if f_name.split('.')[-1] == 'xz':
                f   = lzma.open(f_name, 'rt')
            elif f_name.split('.')[-1] == 'bz2':
                f   = bz2.open(f_name, 'rt')
            elif f_name.split('.')[-1] == 'zst':
                fh              = open(f_name, 'rb')
                dctx            = zstd.ZstdDecompressor(max_window_size=2147483648)
                stream_reader   = dctx.stream_reader(fh)
                f   = io.TextIOWrapper(stream_reader, encoding='utf-8')
            lines   = dict([(name, [])])
            for i, l in enumerate(f):
                if i % 1000000 == 0:
                    print("read %d lines, found %d" % (i, sum([len(ls) for ls in lines.values()])), time() - st_time)
                # for name in subreddit_names:
                #     if name in l:
                lines[name] += [l.strip()]
            if f_name.split('.')[-1] == 'zst':
                fh.close()
            else:
                f.close()
            os.remove(f_name)
            tries_left  = 0
        except EOFError as e:
            sleep(10)
            print("failed reading file %s file, another %d tries" % (f_name, tries_left))
            os.remove(f_name)
            tries_left  -= 1
    print("tokenizing and selecting %s %2f" % (f_name, time() - st_time))
    processed_items = dict([(name, [])])
    if mode == 'submissions':
        key_list    = ['id', 'score', 'url', 'title', 'selftext', "subreddit", 'subreddit_id', "created_utc"]
    else:
        key_list    = ['id', 'link_id', 'parent_id', 'score', 'body', 'subreddit_id', "subreddit", "created_utc"]

    for line in lines[name]:
        reddit_dct  = json.loads(line)
        if reddit_dct.get('num_comments', 1) > 0 and reddit_dct.get('score', 0) and reddit_dct.get('score', 0) >= 2 and (mode == 'submissions' or valid_comment(reddit_dct)):
            reddit_res  = {}
            targeting = False
            for k in key_list:
                if k in ['title', 'selftext', 'body']:
                    if reddit_dct[k].lower() in ['[removed]', '[deleted]']:
                        reddit_dct[k]   = ''
                    txt, url_list       = word_url_tokenize(reddit_dct[k])
                    split_txt = txt.lower().split()
                    if targeted_text(split_txt):
                        targeting = True
                    reddit_res[k]       = (' '.join(txt.split()), url_list)
                    # reddit_res["target"] = targeting
                else:
                    reddit_res[k]       = reddit_dct[k]
            # for k in key_list:
            #     print(reddit_res[k])
            #     if targeted_text(reddit_res[k]):
            #         targeting = True
            #         break
            if targeting:
            #     print("true")
                processed_items[name] += [reddit_res]
    print("Total found %d" % (len(processed_items)), time() - st_time)
    # print(processed_items)
    return processed_items


def post_process(reddit_dct, name=''):
    # remove the ELI5 at the start of explainlikeimfive questions
    start_re    = re.compile('[\[]?[ ]?eli[5f][ ]?[\]]?[]?[:,]?', re.IGNORECASE)
    # dedupe and filter comments
    comments    = [c for i, c in enumerate(reddit_dct['comments']) if len(c['body'][0].split()) >= 8 and c['id'] not in [x['id'] for x in reddit_dct['comments'][:i]]]
    comments    = sorted(comments, key=lambda c: (c['score'], len(c['body'][0].split()), c['id']), reverse=True)
    reddit_dct['comments']  = comments
    # print(reddit_dct['comments'])
    return reddit_dct


def main():
    parser  = argparse.ArgumentParser(description='Subreddit QA pair downloader')
    parser.add_argument('-sy', '--start_year', default=2011, type=int, metavar='N',
                        help='starting year')
    parser.add_argument('-ey', '--end_year', default=2018, type=int, metavar='N',
                        help='end year')
    parser.add_argument('-sm', '--start_month', default=7, type=int, metavar='N',
                        help='starting year')
    parser.add_argument('-em', '--end_month', default=7, type=int, metavar='N',
                        help='end year')
    parser.add_argument('-sr_l', '--subreddit_list', default='["explainlikeimfive"]', type=str,
                        help='subreddit name')
    parser.add_argument('-Q', '--questions_only', action='store_true',
                        help= 'only download submissions')
    parser.add_argument('-A', '--answers_only', action='store_true',
                        help= 'only download comments')
    args        = parser.parse_args()
    ### collect submissions and comments monthly URLs
    date_to_url_submissions = gather_dump_urls(REDDIT_URL,
                                               "submissions")
    date_to_url_comments    = gather_dump_urls(REDDIT_URL,
                                               "comments")
    date_to_urls    = {}
    for k, v in date_to_url_submissions.items():
        date_to_urls[k]    = (v, date_to_url_comments.get(k, ''))
    ### download, filter, process, remove
    subprocess.run(['mkdir', 'reddit_tmp'], stdout=subprocess.PIPE)
    st_time    = time()
    # qa_dict = dict([("name", {})])
    # n_months    = 0
    for year in range(args.start_year, args.end_year + 1):
        st_month    = args.start_month if year == args.start_year else 1
        end_month   = args.end_month if year == args.end_year else 12
        months      = range(st_month, end_month + 1)
        for month in months:
            submissions_url, comments_url   = date_to_urls[(year, month)]
            if args.questions_only:
                try:
                    processed_submissions   = download_and_process(submissions_url,
                                                                   'submissions',
                                                                #    subreddit_names,
                                                                   st_time)
                except FileNotFoundError as e:
                    sleep(60)
                    print("retrying %s once" % (submissions_url))
                    processed_submissions   = download_and_process(submissions_url,
                                                                   'submissions',
                                                                #    subreddit_names,
                                                                   st_time)
                out_file_name = "RS{year}-{month}.json".format(year=year, month=month)
                fo = open(out_file_name, "w")
                jobj = json.dumps(processed_submissions[name], indent=4)
                fo.write(jobj)
                fo.close()
            if args.answers_only:
                try:
                    processed_comments      = download_and_process(comments_url,
                                                                   'comments',
                                                                #    subreddit_names,
                                                                   st_time)
                    # print('pc', processed_comments)
                except FileNotFoundError as e:
                    sleep(60)
                    print("retrying %s once" % (comments_url))
                    processed_comments      = download_and_process(comments_url,
                                                                   'comments',
                                                                #    subreddit_names,
                                                                   st_time)
                out_file_name = "RC{year}-{month}.json".format(year=year, month=month)
                fo = open(out_file_name, "w")
                jobj = json.dumps(processed_comments[name], indent=4)
                fo.write(jobj)
                fo.close()


if __name__ == '__main__':
    main()