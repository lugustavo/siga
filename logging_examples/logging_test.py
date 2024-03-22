import os
from datetime import datetime
import logging.config
import yaml
from jsonschema import validate, ValidationError


def validate_yaml_config(config_file, schema_file):
  """Loads YAML config and validates against JSON schema."""
  with open(config_file, 'r') as file:
    config_data = yaml.safe_load(file)

  with open(schema_file, 'r') as file:
    schema = yaml.safe_load(file)

  try:
    validate(config_data, schema)
    print("Configuration is valid!")
  except ValidationError as e:
    print("Validation Errors: ")
    print(e)
    # Loop through nested errors and print details
    for error in e.context:
      print(f"- {error.message}")


# Usage
validate_yaml_config('logging.yaml', 'logging_schema.yaml')

print('*'*100)

# Load the config file
with open('logging.yaml', 'rt') as f:
    config = yaml.safe_load(f.read())

# Configure the logging module with the config file
print(config.get('handlers').get('file'))
filename = str(config.get('handlers').get('file').get('filename'))
config['handlers']['file']['filename'] = filename.format(os.path.splitext(os.path.basename(__file__))[0],
                                                         datetime.now().strftime('%Y%m%d'))

logging.config.dictConfig(config)

# Get a logger object
logger = logging.getLogger('staging')

for handler in logger.handlers:
    if handler.get_name() == 'file':
        print(handler)

# Log some messages
logger.debug('This is a debug message')
logger.info('This is an info message')
logger.warning('This is a warning message')
logger.error('This is an error message')
logger.critical('This is a critical message')