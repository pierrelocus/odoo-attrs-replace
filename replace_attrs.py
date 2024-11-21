# -*- coding: utf-8 -*-
import re
from pathlib import Path
from lxml import etree

NEW_ATTRS = {'required', 'invisible', 'readonly', 'column_invisible'}


def get_files_recursive(path):
    return (str(p) for p in Path(path).glob('**/*.xml') if p.is_file())


root_dir = input('Enter root directory to check (empty for current directory) : ')
root_dir = root_dir or '.'
all_xml_files = get_files_recursive(root_dir)


def normalize_domain(domain):
    """
    Normalize Domain, taken from odoo/osv/expression.py -> just the part so that & operators are added where needed.
    After that, we can use a part of the def parse() from the same file to manage parenthesis for and/or
    :rtype: list[str|tuple]
    """
    if len(domain) == 1:
        return domain
    result = []
    expected = 1  # expected number of expressions
    op_arity = {'!': 1, '&': 2, '|': 2}
    for token in domain:
        if expected == 0:  # more than expected, like in [A, B]
            result[0:0] = ['&']  # put an extra '&' in front
            expected = 1
        if isinstance(token, (list, tuple)):  # domain term
            expected -= 1
            token = tuple(token)
        else:
            expected += op_arity.get(token, 0) - 1
        result.append(token)
    return result


def stringify_leaf(leaf):
    """
    :param tuple leaf:
    :rtype: str
    """
    stringify = ''
    switcher = False
    case_insensitive = False
    # Replace operators not supported in python (=, like, ilike)
    operator = str(leaf[1])
    # Take left operand, never to add quotes (should be python object / field)
    left_operand = leaf[0]
    # Take care of right operand, don't add quotes if it's list/tuple/set/boolean/number, check if we have a true/false/1/0 string tho.
    right_operand = leaf[2]

    # Handle '=?'
    if operator == '=?':
        if type(right_operand) is str:
            right_operand = f"'{right_operand}'"
        return f"({right_operand} in [None, False] or {left_operand} == {right_operand})"
    # Handle '='
    elif operator == '=':
        if right_operand in (False, []):  # Check for False or empty list
            return f"not {left_operand}"
        elif right_operand == True:  # Check for True using '==' comparison so only boolean values can evaluate to True
            return left_operand
        operator = '=='
    # Handle '!='
    elif operator == '!=':
        if right_operand in (False, []):  # Check for False or empty list
            return left_operand
        elif right_operand == True:  # Check for True using '==' comparison so only boolean values can evaluate to True
            return f"not {left_operand}"
    # Handle 'like' and other operators
    elif 'like' in operator:
        case_insensitive = 'ilike' in operator
        if type(right_operand) is str and re.search('[_%]', right_operand):
            # Since wildcards won't work/be recognized after conversion we throw an error so we don't end up with
            # expressions that behave differently from their originals
            raise Exception("Script doesn't support 'like' domains with wildcards")
        if operator in ['=like', '=ilike']:
            operator = '=='
        else:
            if 'not' in operator:
                operator = 'not in'
            else:
                operator = 'in'
            switcher = True
    if type(right_operand) is str:
        right_operand = f"'{right_operand}'"
    if switcher:
        temp_operand = left_operand
        left_operand = right_operand
        right_operand = temp_operand
    if not case_insensitive:
        stringify = f"{left_operand} {operator} {right_operand}"
    else:
        stringify = f"{left_operand}.lower() {operator} {right_operand}.lower()"
    return stringify


def stringify_attr(stack):
    """
    :param bool|str|int|list stack:
    :rtype: str
    """
    if stack in (True, False, 'True', 'False', 1, 0, '1', '0'):
        return str(stack)
    last_parenthesis_index = max(index for index, item in enumerate(stack[::-1]) if item not in ('|', '!'))
    stack = normalize_domain(stack)
    stack = stack[::-1]
    result = []
    for index, leaf_or_operator in enumerate(stack):
        if leaf_or_operator == '!':
            expr = result.pop()
            result.append('(not (%s))' % expr)
        elif leaf_or_operator in ['&', '|']:
            left = result.pop()
            # In case of a single | or single & , we expect that it's a tag that have an attribute AND a state
            # the state will be added as OR in states management
            try:
                right = result.pop()
            except IndexError:
                res = left + ('%s' % ' and' if leaf_or_operator == '&' else ' or')
                result.append(res)
                continue
            form = '(%s %s %s)'
            if index > last_parenthesis_index:
                form = '%s %s %s'
            result.append(form % (left, 'and' if leaf_or_operator == '&' else 'or', right))
        else:
            result.append(stringify_leaf(leaf_or_operator))
    result = result[0]
    return result


def get_new_attrs(attrs):
    """
    :param str attrs:
    :rtype: dict[bool|str|int]
    """
    new_attrs = {}
    # Temporarily replace dynamic variables (field reference, context value, %()d) in leafs by strings prefixed with '__dynamic_variable__.'
    # This way the evaluation won't fail on these strings and we can later identify them to convert back to  their original values
    escaped_operators = ['=', '!=', '>', '>=', '<', '<=', '=\?', '=like', 'like', 'not like', 'ilike', 'not ilike', '=ilike', 'in', 'not in', 'child_of', 'parent_of']
    attrs = re.sub(f"([\"'](?:{'|'.join(escaped_operators)})[\"']\s*,\s*)([\w\.]+)(?=\s*[\]\)])", r"\1'__dynamic_variable__.\2'", attrs)
    attrs = re.sub(r"(%\([\w\.]+\)d)", r"'__dynamic_variable__.\1'", attrs)
    attrs_dict = eval(attrs.strip())
    for attr in NEW_ATTRS:
        if attr in attrs_dict.keys():
            stringified_attr = stringify_attr(attrs_dict[attr])
            if type(stringified_attr) is str:
                # Convert dynamic variable strings back to their original form
                stringified_attr = re.sub(r"'__dynamic_variable__\.([^']+)'", r"\1", stringified_attr)
            new_attrs[attr] = stringified_attr
    return new_attrs


autoreplace = input('Do you want to auto-replace attributes ? (y/n) (empty == no) (will not ask confirmation for each file) : ') or 'n'
nofilesfound = True
ok_files = []
nok_files = []


def get_parent_etree_node(root_node, target_node):
    """
    Returns the parent node of a given node, and the index and indentation of the target node in the parent node's direct child nodes list
    :param xml.etree.ElementTree.Element root_node:
    :param xml.etree.ElementTree.Element target_node:
    :returns: index, parent_node, indentation
    :rtype: (int, xml.etree.ElementTree.Element, str)
    """
    for parent_elem in root_node.iter():
        previous_child = False
        for i, child in enumerate(list(parent_elem)):
            if child == target_node:
                if previous_child:
                    indent = previous_child.tail
                else:
                    # For the first child element it's the text in between the parent's opening tag and the first child that determines indentation
                    indent = parent_elem.text
                return i, parent_elem, indent
            previous_child = child


def get_combined_invisible_condition(existing_invisible_condition, states_string):
    """
    :param str existing_invisible_condition: invisible attribute condition already present on the same tag as the states
    :param str states_string: string of the form 'state1,state2,...'
    """
    states_list = re.split(r"\s*,\s*", states_string.strip())
    states_to_add = f"state not in {states_list}"
    if not states_string:
        return existing_invisible_condition
    if existing_invisible_condition:
        if existing_invisible_condition.endswith('or') or existing_invisible_condition.endswith('and'):
            combined_invisible_condition = f"{existing_invisible_condition} {states_to_add}"
        else:
            combined_invisible_condition = f"{existing_invisible_condition} or {states_to_add}"
    else:
        combined_invisible_condition = states_to_add
    return combined_invisible_condition


for xml_file in all_xml_files:
    try:
        with open(xml_file, 'rb') as f:
            contents = f.read().decode('utf-8')
            f.close()
            if not 'attrs' in contents and not 'states' in contents:
                continue
            convert_line_separator_back_to_windows = False
            if '\r\n' in contents:
                # The ElementTree parser parses line separators as '\n', so to ensure we don't change the line separator
                # when updating the file we should convert the '\n' back to '\r\n' after serializing the ElementTree
                convert_line_separator_back_to_windows = True
            # etree can't parse xml strings with an encoding declaration, so first we strip this from the file content
            # we'll then re-add the declaration once we convert the ElementTree back to its string representation
            has_encoding_declaration = False
            if encoding_declaration := re.search(r"\A.*<\?xml.*?encoding=.*?\?>\s*", contents, re.DOTALL):
                has_encoding_declaration = True
                contents = re.sub(r"\A.*<\?xml.*?encoding=.*?\?>\s*", "", contents, re.DOTALL)
            # Parse the document int an ElementTree
            doc = etree.fromstring(contents)
            tags_with_attrs = doc.xpath("//*[@attrs]")
            attribute_tags_with_attrs = doc.xpath("//attribute[@name='attrs']")
            tags_with_states = doc.xpath("//*[@states]")
            attribute_tags_with_states = doc.xpath("//attribute[@name='states']")
            if not (tags_with_attrs or attribute_tags_with_attrs or tags_with_states or attribute_tags_with_states):
                continue
            print('\n#############################' + ((6 + len(xml_file)) * '#'))
            print('##### Taking care of file -> %s' % xml_file)
            print('\n##### Current tags found #####\n')
            for t in tags_with_attrs + attribute_tags_with_attrs + tags_with_states + attribute_tags_with_states:
                print(etree.tostring(t, encoding='unicode'))

            nofilesfound = False
            # Management of tags that have attrs=""
            for tag in tags_with_attrs:
                attrs = tag.attrib.get('attrs')
                new_attrs = get_new_attrs(attrs)
                all_attributes = []
                # TODO: combine existing and new invisible, required, readonly and column_invisible attributes
                # If both an attrs and one of these attributes are present at the same time, if the attribute is True
                # then it overrides the domain in the attrs dict. If it is false then the value in the attrs dict has
                # priority instead
                for attr_name, attr_value in list(tag.attrib.items()):
                    # We have to rebuild the attributes to maintain their order
                    if attr_name == 'attrs':
                        # Insert the new attributes in their original position, in their original order
                        ordered_new_attrs = re.findall(rf"['\"]({'|'.join(NEW_ATTRS)})['\"]\s*:", attrs)
                        for new_attr in ordered_new_attrs:
                            all_attributes.append((new_attr, new_attrs.get(new_attr)))
                    else:
                        all_attributes.append((attr_name, attr_value))
                tag.attrib.clear()
                tag.attrib.update(all_attributes)

            # Management of attributes name="attrs"
            attribute_tags_with_attrs_after = []
            for attribute_tag in attribute_tags_with_attrs:
                tag_index, parent_tag, indent = get_parent_etree_node(doc, attribute_tag)
                tail = attribute_tag.tail or ''
                attrs = attribute_tag.text
                new_attrs = get_new_attrs(attrs)
                # Insert the new attributes tags in their original position, in their original order in that attrs dict
                ordered_new_attrs = re.findall(rf"['\"]({'|'.join(NEW_ATTRS)})['\"]\s*:", attrs)
                for new_attr in ordered_new_attrs:
                    new_tag = etree.Element('attribute', attrib={
                        'name': new_attr
                    })
                    new_tag.text = str(new_attrs.get(new_attr))
                    # First set the tail so that all following new attribute tags have the same indentation
                    new_tag.tail = indent
                    parent_tag.insert(tag_index, new_tag)
                    attribute_tags_with_attrs_after.append(new_tag)
                    tag_index += 1
                # Then set the tail of the last added tag so that the following tags maintain their original indentation
                new_tag.tail = tail
                parent_tag.remove(attribute_tag)

            # Management of tags that have states=""
            for state_tag in tags_with_states:
                base_invisible = ''
                invisible_attribute = state_tag.get('invisible', '')
                new_invisible_attr = get_combined_invisible_condition(invisible_attribute,
                                                                      state_tag.attrib.get('states', ''))
                all_attributes = []
                for attr_name, attr_value in list(state_tag.attrib.items()):
                    # We have to rebuild the attributes to maintain their order
                    if attr_name == 'invisible' or (attr_name == 'states' and not invisible_attribute):
                        # Update invisible attribute if it exists, else replace the states attribute
                        all_attributes.append(('invisible', new_invisible_attr))
                    elif attr_name != 'states':
                        # Don't keep the states attribute
                        all_attributes.append((attr_name, attr_value))
                state_tag.attrib.clear()
                state_tag.attrib.update(all_attributes)

            # Management of attributes name="states"
            attribute_tags_with_states_after = []
            for attribute_tag_states in attribute_tags_with_states:
                tag_index, parent_tag, indent = get_parent_etree_node(doc, attribute_tag_states)
                tail = attribute_tag_states.tail
                if invisible_tags := parent_tag.xpath("./attribute[@name='invisible']"):
                    attribute_tag_invisible = invisible_tags[0]
                    if tag_index > 0:
                        invisible_tag_index, invisible_parent_tag, invisible_indent = get_parent_etree_node(doc, attribute_tag_invisible)
                        if invisible_tag_index == tag_index - 1:
                            # If the attrs and invisible tags directly follow each other the tail of the invisible tag
                            # has to be updated, since otherwise the element after the states tag will get indented the
                            # same as the states tag
                            attribute_tag_invisible.tail = attribute_tag_states.tail
                else:
                    # If no invisible attribute tag exists, add it in place of the original states attribute tag
                    attribute_tag_invisible = etree.Element('attribute', attrib={'name': 'invisible'})
                    attribute_tag_invisible.tail = tail
                    parent_tag.insert(tag_index, attribute_tag_invisible)
                parent_tag.remove(attribute_tag_states)
                invisible_condition = get_combined_invisible_condition(attribute_tag_invisible.text,
                                                                       attribute_tag_states.text)
                attribute_tag_invisible.text = invisible_condition
                attribute_tags_with_states_after.append(attribute_tag_invisible)

            print('\n##### Will be replaced by #####\n')
            for t in tags_with_attrs + attribute_tags_with_attrs_after + tags_with_states + attribute_tags_with_states_after:
                print(etree.tostring(t, encoding='unicode'))
            print('\n###############################\n')
            if autoreplace.lower()[0] == 'n':
                confirm = input('Do you want to replace? (y/n) (empty == no) : ') or 'n'
            else:
                confirm = 'y'
            if confirm.lower()[0] == 'y':
                with open(xml_file, 'wb') as rf:
                    xml_string = etree.tostring(doc, encoding='utf-8', xml_declaration=has_encoding_declaration)
                    if convert_line_separator_back_to_windows:
                        xml_string = xml_string.replace(b"\n", b"\r\n")
                    rf.write(xml_string)
                    ok_files.append(xml_file)
    except Exception as e:
        nok_files.append((xml_file, e))


print('\n################################################')
print('################## Run  Debug ##################')
print('################################################')

if nofilesfound:
    print('No XML Files with "attrs" or "states" found in dir " %s "' % root_dir)

print('Succeeded on files')
for file in ok_files:
    print(file)
if not ok_files:
    print('No files')
print('')
print('Failed on files')
for file in nok_files:
    print(file[0])
    print('Reason: ', file[1])
if not nok_files:
    print('No files')
