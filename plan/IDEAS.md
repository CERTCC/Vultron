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

## Config files should be YAML and loaded into a structured config object

When we have a need for config files, we should use YAML for readability and
ease of editing. We should also load the YAML config into a structured
config object using Pydantic so that we can enforce types and have a clear
schema for our configuration. Rough sketch of the workflow: Load YAML config
into a dict (`config_dict=yaml.safe_load()`), then pass that dict to a Pydantic
model (`Config.model_validate(config_dict)`) that defines the schema for our
configuration. This can also allow us to have nested configuration sections
for different components, and modularity in how we define and validate
config for different adapters or features.
