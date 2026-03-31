# Project Ideas

## Database file for TinyDB should be configurable

The original implementation just had a fixed `mydb.json` file acting as the
TinyDB database. This is fine for a simple demo, but for real-world use, it
really needs to be configurable. Whatever solution we apply here should
carry through to how we'd specify the configuration for other adapters as
well like mongodb, etc. So this seems to argue in favor of a dedicated
configuration block in the config file for the data layer, where it
specifies not only which database adapter to use, but also the relevant
configuration details for that adapter (which will include the db file path
for TinyDB, but would include other details for other adapters).
