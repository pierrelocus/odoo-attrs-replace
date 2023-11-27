# -*- coding: utf-8 -*-

import os
from bs4 import BeautifulSoup as bs

def get_files_recursive(path):
    xml_files = []
    for item in os.listdir(path):
        if os.path.isfile(os.path.join(path, item)) and item.endswith('.xml'):
            xml_files.append(os.path.join(path, item))
        if os.path.isdir(os.path.join(path, item)):
            xml_files.extend(get_files_recursive(os.path.join(path, item)))
    return xml_files

root_dir = input('Enter root directory to check (empty for current directory) : ')
root_dir = root_dir or '.'
all_xml_files = get_files_recursive(root_dir)

def stringify_attr(stack):
    if stack in (True, False, 'True', 'False', 1, 0, '1', '0'):
        return stack
    keep_or_and = []
    stringified = ''
    for index, i in enumerate(stack):
        if isinstance(i, str) and i in '|&':
                keep_or_and.append(i)
        else:
                operator = str(i[1])
                if operator == '=':
                    operator = '=='
                stringify = str(i[0]) + ' ' + operator + ' '
                operand = i[2]
                if operand in ('True', 'False', '1', '0', True, False, 1, 0) or type(operand) in (list, tuple, set):
                    stringify += str(operand)
                else:
                    stringify += "'"+operand+"'"
                if len(keep_or_and):
                    stringify += ' and ' if keep_or_and.pop()=='&' else ' or '
                elif index < len(stack) -1:
                    stringify += ' and '
                stringified += stringify
    return stringified

def get_new_attrs(attrs):
    new_attrs = {}
    attrs_dict = eval(attrs)
    for attr in {'required', 'invisible', 'readonly'}:
        if attr in attrs_dict.keys():
            new_attrs[attr] = stringify_attr(attrs_dict[attr])
    return new_attrs
            

for xml_file in all_xml_files:
    print('Taking Care of XML File : %s' % xml_file)
    with open(xml_file, 'rb') as f:
        contents = f.read().decode('utf-8')
        f.close()
        if not 'attrs' in contents:
            continue
        soup = bs(contents, 'xml')
        tags = soup.select('[attrs]')
        if not tags:
            continue
        print(tags)
        print('Will be replaced by')
        for tag in tags:
            attrs = tag['attrs']
            new_attrs = get_new_attrs(attrs)
            del tag['attrs']
            for new_attr in new_attrs.keys():
                tag[new_attr] = new_attrs[new_attr]
        print(tags)
        confirm = input('Do you want to replace? (y/n) : (empty == no)')
        confirm = confirm or 'n'
        if confirm.lower()[0] == 'y':
            with open(xml_file, 'wb') as rf:
                html = soup.prettify("utf-8")
                rf.write(html)
                rf.close()
