"""
Box API core module

Docs: http://developers.box.com/docs
"""

import json
import os
import requests
import types
import urlparse

import sanction.client

import auth


API_URL = "https://api.box.com/2.0"
API_UPLOAD_URL = "https://upload.box.com/api/2.0"


class Session(object):
    """A connection to the Box API."""

    def __init__(self, api_key, auth_token=None):
        self.api_key = api_key
        self.auth_token = auth_token

    def apply_new_authtoken(self):
        self.ticket = auth.get_ticket(self.api_key)
        self.auth_url = auth.open_for_auth_ticket(self.ticket)

    def authorize(self, ticket):
        result = auth.get_auth_token(self.api_key, ticket)
        try:
            self.auth_token = result['response']['auth_token']['value']
        except:
            raise Exception("[Error] Authorizing failed.")

    def action(self, path, base_path=API_URL, method='GET', headers=None, params=None, data=None, raw_data=True, files=None):
        """
        Run an action on the server
        """
        options = {
            "headers": {"Authorization": "BoxAuth api_key=%s&auth_token=%s" % (self.api_key, self.auth_token)},
        }

        if headers:
            options["headers"].update(headers)
        if params:
            options["params"] = params
        if data:
            if raw_data:
                options["data"] = json.dumps(data)
            else:
                options["data"] = data
        if files:
            options["files"] = files

        response = requests.request(method, base_path + path, **options)
        try:
            return response.json()
        except ValueError:
            content = response.content
            if content:
                return content
            else:
                return None

    def numeric_id_to_object(self, object_):
        """
        Convert a numeric id to an object. Do all appropriate validations.

        The function allows for an object to be passed in and it will do
        necessary validation to make sure the object has the appropriate id
        key and that the key is of valid type.
        """
        if isinstance(object_, int) or (isinstance(object_, types.StringTypes) and object_.isdigit()):
            object_ = {'id': object_}
        elif isinstance(object_, dict):
            if 'id' not in object_:
                raise Exception('Id required.')
            if not (isinstance(object_['id'], int) or
                    (isinstance(object_['id'], types.StringTypes) and object_['id'].isdigit())):
                raise Exception('Id must be numeric, not %s.' % type(object_['id']).__name__)
        else:
            raise TypeError('Invalid type (%s) for object or id.' % type(object_).__name__)

        return object_

    #
    # API Helper functions.
    # These make for more human useable functions to interact with the API.
    #

    def create_folder(self, name, parent):
        """
        Create a folder
        http://developers.box.com/docs/#folders-create-a-new-folder
        """
        parent = self.numeric_id_to_object(parent)
        return self.action('/folders', method='POST', data={"name":name, "parent":parent})

    def folder_info(self, folder_id):
        """
        Get information for a single folder
        http://developers.box.com/docs/#folders-get-information-about-a-folder
        """
        if not isinstance(folder_id, int):
            raise TypeError('The folder id should be an integer, not %s' % type(folder_id).__name__)
        return self.action('/folders/%d' % folder_id)

    def upload_file(self, path, parent):
        """
        Upload a single file to a folder
        http://developers.box.com/docs/#files-upload-a-file
        """
        # TODO: Support Content-MD5 header and content_created_at and content_modified_at attributes
        if not os.path.exists(path):
            raise ValueError('The file at %s does not exist.' % path)

        parent = self.numeric_id_to_object(parent)
        fh = open(path, 'rb')
        response = self.action(
            "/files/content", base_path=API_UPLOAD_URL, method="POST",
            data={
                "parent_id": parent['id'],
                "filename": os.path.basename(path),
            },
            raw_data=False,
            files={"filename": fh}
        )
        fh.close()
        return response

    def download_file(self, file_id, version_id=None):
        """
        Download a single file
        http://developers.box.com/docs/#files-download-a-file
        """
        if not isinstance(file_id, int):
            raise TypeError('The file id should be an integer, not %s' % type(file_id).__name__)

        if version_id is not None and not isinstance(version_id, int):
            raise TypeError('The file id should be an integer, not %s' % type(version_id).__name__)

        url = "/files/%d/content" % file_id

        if version_id is None:
            response = self.action(url)
        else:
            response = self.action(url, params={"version": version_id})

        return response

    def file_info(self, file_id):
        """
        Get info about a file
        http://developers.box.com/docs/#files-get
        """
        if not isinstance(file_id, int):
            raise TypeError('The file id should be an integer, not %s' % type(file_id).__name__)
        return self.action("/files/%s" % file_id)

    def upload_file_version(self, path, file_id, etag):
        """
        Upload a new version of a file
        http://developers.box.com/docs/#files-upload-a-new-version-of-a-file
        """
        # TODO: Support content_modified_at field
        if not os.path.exists(path):
            raise ValueError('The file at %s does not exist.' % path)

        if not isinstance(file_id, int):
            raise TypeError('The file id should be an integer, not %s' % type(file_id).__name__)

        if not isinstance(etag, int):
            raise TypeError('The etag id should be an integer, not %s' % type(etag).__name__)

        fh = open(path, 'rb')
        response = self.action("/files/%d/content" % file_id, base_path=API_UPLOAD_URL, method="POST",
            headers={"If-Match": etag},
            data={
                "name": os.path.basename(path),
            },
            raw_data=False,
            files={"filename": fh}
        )
        fh.close()
        return response

    def view_file_versions(self, file_id):
        """
        Get a list of a file's versions
        http://developers.box.com/docs/#files-view-versions-of-a-file
        """
        raise NotImplementedError('view_file_versions is not implemented.')

    def update_file_infomation(self):
        """
        Update a file's information / metadata
        http://developers.box.com/docs/#files-update-a-files-information
        """
        raise NotImplementedError('update_file_infomation is not implemented.')

    def delete_file(self, file_id, etag=None):
        """
        Delete a file
        http://developers.box.com/docs/#files-delete-a-file
        """
        if not isinstance(file_id, int):
            raise TypeError('The file id should be an integer, not %s' % type(file_id).__name__)

        if etag is not None and not isinstance(etag, int):
            raise TypeError('The etag id should be an integer, not %s' % type(etag).__name__)

        if etag:
            return self.action("/files/%d" % file_id, method="DELETE", headers={"If-Match": etag})
        else:
            return self.action("/files/%d" % file_id, method="DELETE")
