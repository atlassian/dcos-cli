import contextlib
import inspect
import json
import logging
import os
import re
import shutil
import sys
import tempfile

import jsonschema
import six
from dcos.api import constants, errors


@contextlib.contextmanager
def tempdir():
    """A context manager for temporary directories.

    The lifetime of the returned temporary directory corresponds to the
    lexical scope of the returned file descriptor.

    :return: Reference to a temporary directory
    :rtype: file descriptor
    """

    tmpdir = tempfile.mkdtemp()
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def which(program):
    """Returns the path to the named executable program.

    :param program: The program to locate:
    :type program: str
    :rtype: str or Error
    """

    def is_exe(file_path):
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

    file_path, filename = os.path.split(program)
    if file_path:
        if is_exe(program):
            return program
    elif constants.PATH_ENV in os.environ:
        for path in os.environ[constants.PATH_ENV].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def process_executable_path():
    """Returns the real path to the program for this running process

    :returns: the real path to the program
    :rtype: str
    """

    return os.path.realpath(inspect.stack()[-1][1])


def dcos_path():
    """Returns the real path to the DCOS path based on the executable

    :returns: the real path to the DCOS path
    :rtype: str
    """
    return os.path.dirname(os.path.dirname(process_executable_path()))


def configure_logger_from_environ():
    """Configure the program's logger using the environment variable

    :returns: An Error if we were unable to configure logging from the
              environment; None otherwise
    :rtype: dcos.api.errors.DefaultError
    """

    return configure_logger(os.environ.get(constants.DCOS_LOG_LEVEL_ENV))


def configure_logger(log_level):
    """Configure the program's logger.

    :param log_level: Log level for configuring logging
    :type log_level: str
    :returns: An Error if we were unable to configure logging; None otherwise
    :rtype: dcos.api.errors.DefaultError
    """
    if log_level is None:
        logging.disable(logging.CRITICAL)
        return None

    if log_level in constants.VALID_LOG_LEVEL_VALUES:
        logging.basicConfig(
            format='%(message)s',
            stream=sys.stderr,
            level=log_level.upper())
        return None

    msg = 'Log level set to an unknown value {!r}. Valid values are {!r}'
    return errors.DefaultError(
        msg.format(log_level, constants.VALID_LOG_LEVEL_VALUES))


def get_logger(name):
    """Get a logger

    :param name: The name of the logger. E.g. __name__
    :type name: str
    :returns: The logger for the specified name
    :rtype: logging.Logger
    """

    return logging.getLogger(name)


def load_json(reader):
    """Deserialize a reader into a python object

    :param reader: the json reader
    :type reader: a :code:`.read()`-supporting object
    :returns: the deserialized JSON object
    :rtype: (any, Error) where any is one of dict, list, str, int, float or
            bool
    """

    try:
        return (json.load(reader), None)
    except:
        error = sys.exc_info()[0]
        logger = get_logger(__name__)
        logger.error(
            'Unhandled exception while loading JSON: %r',
            error)
        return (None, errors.DefaultError('Error loading JSON.'))


def load_jsons(value):
    """Deserialize a string to a python object

    :param value: The JSON string
    :type value: str
    :returns: The deserialized JSON object
    :rtype: (any, Error) where any is one of dict, list, str, int, float or
            bool
    """

    try:
        return (json.loads(value), None)
    except:
        error = sys.exc_info()[0]
        logger = get_logger(__name__)
        logger.error(
            'Unhandled exception while loading JSON: %r -- %r',
            value,
            error)
        return (None, errors.DefaultError('Error loading JSON.'))


def validate_json(instance, schema):
    """Validate an instance under the given schema.

    :param instance: the instance to validate
    :type instance: dict
    :param schema: the schema to validate with
    :type schema: dict
    :returns: an error if the validation failed; None otherwise
    :rtype: Error
    """

    # TODO: clean up this hack
    #
    # The error string from jsonschema already contains improperly formatted
    # JSON values, so we have to resort to removing the unicode prefix using
    # a regular expression.
    def hack_error_message_fix(message):
        # This regular expression matches the character 'u' followed by the
        # single-quote character, all optionally preceded by a left square
        # bracket, parenthesis, curly brace, or whitespace character.
        return re.compile("([\[\(\{\s])u'").sub(
            "\g<1>'",
            re.compile("^u'").sub("'", message))

    def sort_key(ve):
        return six.u(hack_error_message_fix(ve.message))

    validator = jsonschema.Draft4Validator(schema)
    validation_errors = list(validator.iter_errors(instance))
    validation_errors = sorted(validation_errors, key=sort_key)

    def format(error):
        message = 'Error: {}\n'.format(hack_error_message_fix(error.message))
        if len(error.absolute_path) > 0:
            message += 'Path: {}\n'.format('.'.join(error.absolute_path))
        message += 'Value: {}'.format(json.dumps(error.instance))
        return message

    formatted_errors = [format(e) for e in validation_errors]

    if len(formatted_errors) is 0:
        return None
    else:
        errors_as_str = str.join('\n\n', formatted_errors)
        return errors.DefaultError(errors_as_str)


def parse_int(string):
    """Parse string and an integer

    :param string: string to parse as an integer
    :type string: str
    :returns: the interger value of the string
    :rtype: (int, Error)
    """

    try:
        return (int(string), None)
    except:
        error = sys.exc_info()[0]
        logger = get_logger(__name__)
        logger.error(
            'Unhandled exception while parsing string as int: %r -- %r',
            string,
            error)
        return (None, errors.DefaultError('Error parsing string as int'))