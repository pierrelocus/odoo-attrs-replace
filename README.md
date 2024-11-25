# Odoo Attrs replacer
As Odoo changed the attrs to (no more attrs) in v17, as well as combining states into invisible attributes, I created this little script to help you replace all attrs and states in your XML files with corresponding attributes in the XML directly.

## Dependencies

Simply install with 
```shell
pip install lxml
```
OR
```shell
pip install -r requirements.txt
```
## Usage

Launch the python script
```shell
python3 replace_attrs.py
```

It will ask you the root directory to check for `XML` files. You can give a project's absolute path.

If no arguments are given, it will use the current directory.

The script will ask you, for each file, if you want to replace all `attrs=` and `states=` with related `attrs` (invisible,readonly,required,column_invisible) - (invisible concatenation or creation for `states`) in the tag (for all instances per tag).

Unless you chose in the beginning 'y' for auto-replace (don't ask for each file)

## Important before running the script

In Odoo 17 the invisible attributes on fields in tree views will no longer hide the whole column, only the cell. Hiding the whole column is now done with the column_invisible attribute instead.
Before running this script, the user should first convert all those invisible attributes on tree fields to column_invisible instead. If this is not done first, those attributes will be combined with the invisible attributes in the attrs dict instead, and thus lost (though it will just be every cell in the column that will be made invisible instead of the column itself, so in essence the values will still be made invisible using the same old conditions).

## Found a flaw ?

Please open an Issue or make a PR or contact me on LinkedIn (Pierre Locus)

Please include a **[Minimal Reproducible Example](https://en.wikipedia.org/wiki/Minimal_reproducible_example)** in your PR if you find a bug.

Thanks in advance!

## TODO:
  - [ ] Support missing operators "child_of", "parent_of" (less used than the others already supported)

## Contributors

Thank you for your contributions:

  -  @lorenuars19 for the better README
  -  @artygo8 for the faster and cleaner get_files_recursive function
  -  @elhamdaoui because details are important
  -  @ThomasDePontieuSomko clear MVP in this repo, many thanks for all the enhancements and refactors

