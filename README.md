# Odoo Attrs replacer
As Odoo changed the attrs to (no more attrs) in v17, I created this little script to help you replace all attrs in your XML files with corresponding attributes in the XML directly.

## Dependencies

Simply install with 
```shell
pip install beautifulsoup4
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

## Found a flaw ?

Please open an Issue or make a PR or contact me on LinkedIn (Pierre Locus)

Please include a **[Minimal Reproducible Example](https://en.wikipedia.org/wiki/Minimal_reproducible_example)** in your PR if you find a bug.

Thanks in advance!

## TODO:
  - [ ] Support missing operators "=?", "child_of", "parent_of" (less used than the others already supported)

## Contributors

Thank you for your contributions:

  -  @lorenuars19 for the better README
  -  @artygo8 for the faster and cleaner get_files_recursive function
