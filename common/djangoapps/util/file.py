"""
Utility methods related to file handling.
"""

from datetime import datetime
import os
from pytz import UTC
import urllib

from django.core.exceptions import PermissionDenied
from django.core.files.storage import DefaultStorage, get_valid_filename
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext


class FileValidationException(Exception):
    """
    An exception thrown during file validation.
    """
    pass


def store_uploaded_file(
        request, file_key, allowed_file_types, base_storage_filename, max_file_size=2000000, validator=None,
):
    """
    Stores an uploaded file to django file storage.

    Args:
        request (HttpRequest): A request object from which a file will be retrieved.
        file_key (str): The key for retrieving the file from `request.FILES`. If no entry exists with this
            key, a `ValueError` will be thrown.
        allowed_file_types (list): a list of allowable file type extensions. These should start with a period
            and be specified in lower-case. For example, ['.txt', '.csv']. If the uploaded file does not end
            with one of these extensions, a `PermissionDenied` exception will be thrown. Note that the uploaded file
            extension does not need to be lower-case.
        base_storage_filename (str): the filename to be used for the stored file, not including the extension.
            The same extension as the uploaded file will be appended to this value.
        max_file_size (int): the maximum file size in bytes that the uploaded file can be. If the uploaded file
            is larger than this size, a `PermissionDenied` exception will be thrown. Default value is 2000000 bytes
            (2 MB).
        validator (function): an optional validation method that, if defined, will be passed the stored file (which
            is copied from the uploaded file). This method can do validation on the contents of the file and throw
            a `FileValidationException` if the file is not properly formatted. If any exception is thrown, the stored
            file will be deleted before the exception is re-raised. Note that the implementor of the validator function
            should take care to close the stored file if they open it for reading.

    Returns:
        Storage: the file storage object where the file can be retrieved from
        str: stored_file_name: the name of the stored file (including extension)

    """

    if file_key not in request.FILES:
        raise ValueError("No file uploaded with key '" + file_key + "'.")

    uploaded_file = request.FILES[file_key]
    try:
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        if not file_extension in allowed_file_types:
            file_types = "', '".join(allowed_file_types)
            msg = ungettext(
                "The file must end with the extension '{file_types}'.",
                "The file must end with one of the following extensions: '{file_types}'.",
                len(allowed_file_types)).format(file_types=file_types)
            raise PermissionDenied(msg)

        if uploaded_file.size > max_file_size:
            msg = _("Maximum upload file size is {file_size} bytes.").format(file_size=max_file_size)
            raise PermissionDenied(msg)

        stored_file_name = base_storage_filename + file_extension

        file_storage = DefaultStorage()
        # use default storage to store file
        file_storage.save(stored_file_name, uploaded_file)

        if validator:
            try:
                validator(file_storage, stored_file_name)
            except:
                file_storage.delete(stored_file_name)
                raise

    finally:
        uploaded_file.close()

    return file_storage, stored_file_name


# pylint: disable=invalid-name
def course_and_time_based_filename_generator(course_id, base_name):
    """
    Generates a filename (without extension) based on the current time and the supplied filename.

    Args:
        course_id (object): A course identification object that must support conversion to unicode.
        base_name (str): A name describing what type of file this is. Any characters that are not safe for
            filenames will be converted per django.core.files.storage.get_valid_filename (Specifically,
            leading and trailing spaces are removed; other  spaces are converted to underscores; and anything
            that is not a unicode alphanumeric, dash, underscore, or dot, is removed).

    Returns:
        str: a concatenation of the course_id (with backslashes replace by underscores), the base_name,
            and the current time. Note that there will be no extension.

    """
    return u"{course_prefix}_{base_name}_{timestamp_str}".format(
        course_prefix=urllib.quote(unicode(course_id).replace("/", "_")),
        base_name=get_valid_filename(base_name),
        timestamp_str=datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")  # pylint: disable=maybe-no-member
    )