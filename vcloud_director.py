"""
VCloud Director client class.
"""
import itertools
import logging
import time
import xml.etree.ElementTree as ET
import progressbar

from config import BASE_URL, VCD_URL
from lxml import objectify
from vcloud_director_base import VCloudDirectorBase

logging.basicConfig(level=logging.INFO, format='%(name)s %(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)

VCD_AUTH_HDR = 'x-vcloud-authorization'


def anyTrue(pred, seq):
    """Returns True if a True predicate is found, False otherwise.
    Quits as soon as the first True is found.
    """
    return True in itertools.imap(pred, seq)


class VCloudDirector(VCloudDirectorBase):

    def list_orgs(self):
        """Get a list of organizations while logged in as the root or
        system user.
        """
        retval = []
        response = self.session.get('{}/{}'.format(BASE_URL, '/org'))
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for child in root:
                if child.attrib:
                    retval.append(child.attrib)
        return retval

    def list_org_links(self, org):
        """Get the list of links for each org.
        """
        retval = []
        response = self.session.get(org['href'])
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for child in root:
                if child.attrib and child.attrib.get('name'):
                    retval.append(child.attrib)
        return retval

    def list_org_catalog_links(self, catalog):
        """Get the list of links for a catalog.
        """
        retval = []
        response = self.session.get(catalog['href'])
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for element in root:
                for all_tags in element.findall('.//'):
                    if all_tags.attrib['type'] == 'application/vnd.vmware.vcloud.catalogItem+xml':
                        retval.append(all_tags.attrib['name'])
        return retval

    def get_upload_catalog_links(self, catalog, tagtype):
        """Get the list of links for a specified catalog.
        """
        retval = []
        response = self.session.get(catalog['href'])
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for child in root:
                if child.attrib.get('type') == tagtype and child.attrib.get('href', '').endswith('upload'):
                    retval.append(child.attrib)
        return retval

    def upload_media(self, catalog, filename, filesize, description):
        """Upload ISO media to the catalog.
        """
        self.session.headers.update({'Content-Type': 'application/vnd.vmware.vcloud.media+xml'})
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Media
                xmlns="http://www.vmware.com/vcloud/v1.5"
                name="{}"
                size="{}"
                imageType="iso">
                <Description>{}</Description>
            </Media>'''.format(filename, filesize, description)

        response = self.session.post(catalog['href'], data=xml)

        if response.status_code in [200, 201]:
            root = ET.fromstring(str(response.text))
            for element in root:
                if 'Entity' in element.tag:  # and element.attrib.get('name') == filename:
                    # Return the GET link for progress
                    progress_href = element.attrib['href']
                    response = self.session.get(element.attrib['href'])
                    root = ET.fromstring(str(response.text))

                    for element in root:
                        for all_tags in element.findall('.//'):
                            if all_tags.attrib.get('rel') == 'upload:default':
                                with open(filename) as f:
                                    data = f.read()
                                    response = self.session.put(all_tags.attrib['href'], data=data)
                                break
                    break
        return progress_href

    def upload_template(self, catalog, filename, shortname, description):
        """Upload vApp template to the catalog.
        """
        self.session.headers.update({'Content-Type': 'application/vnd.vmware.vcloud.uploadVAppTemplateParams+xml'})
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
            <UploadVAppTemplateParams
                name="{}"
                xmlns="http://www.vmware.com/vcloud/v1.5"
                xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1">
                <Description>{}</Description>
            </UploadVAppTemplateParams>'''.format(shortname, description)

        response = self.session.post(catalog['href'], data=xml)

        if response.status_code in [200, 201]:
            root = ET.fromstring(str(response.text))
            for element in root:
                if 'Entity' in element.tag:  # and element.attrib.get('name') == filename:
                    # Return the GET link for progress
                    vapp_template_url = element.attrib['href']
                    response = self.session.get(vapp_template_url)

                    # Extract the OVF descriptor
                    root = ET.fromstring(str(response.text))
                    uploads = {}

                    for element, all_tags in ((ele, alltg) for ele in root for alltg in ele.findall('.//')):
                        if all_tags.tag.endswith('Link'):
                            print("--> {}".format(all_tags.attrib.get('href')))
                            if all_tags.attrib.get('href', '').endswith('descriptor.ovf') and all_tags.attrib.get('rel') == 'upload:default':
                                print(all_tags.attrib)
                                descriptor_url = all_tags.attrib['href']
                                uploads['descriptor.ovf'] = {
                                    'url': descriptor_url,
                                    # 'size': all_tags.attrib['size']
                                    'status': 'UPLOADED'
                                }

                                # Upload the OVF descriptor
                                self.session.headers.update({'Content-Type': 'text/xml'})
                                filename = '/home/rhemmers/OVA/tmp/ovftool-tst-demo.ovf'
                                print("********************************")
                                print("*** Uploading descriptor ovf ***")
                                print("********************************")
                                with open(filename) as f:
                                    data = f.read()
                                    response = self.session.put(descriptor_url, data=data)
                                    print('  > response code: {}'.format(response.status_code))
                                    print(response.text)

                                # Retrieve the template to see additional upload URLs
                                print("*****************************************")
                                print("*** Retrieving Additional Upload URLs ***")
                                print("... using vapp template url: {}".format(vapp_template_url))
                                print("*****************************************")
                                self.session.headers.update({'Content-Type': 'application/vnd.vmware.vcloud.vAppTemplate+xml'})
                                response = self.session.get(vapp_template_url)
                                print(response.text)

                                done = False
                                while not done:
                                    response = self.session.get(vapp_template_url)
                                    root = objectify.fromstring(str(response.text))

                                    for key, value in root.items():
                                        if key == 'ovfDescriptorUploaded':
                                            if value == 'true':
                                                done = True

                                    time.sleep(1)

                                xmlData = objectify.fromstring(str(response.text))

                                for subelem in xmlData.iter(tag='{http://www.vmware.com/vcloud/v1.5}File'):
                                    # file_transferred = subelem.get('bytesTransferred')
                                    file_size = subelem.get('size')
                                    file_name = subelem.get('name')

                                    for link in subelem.iter(tag='{http://www.vmware.com/vcloud/v1.5}Link'):
                                        if file_name not in uploads:
                                            uploads[file_name] = {
                                                'url': link.get('href'),
                                                'name': file_name,
                                                'size': file_size,
                                                'status': ''
                                            }

                                break

                    # Downloads remaining ova files, i.e., vmdk
                    print('*********************************')
                    print('***** Downloading VMDK file *****')
                    print('*********************************')
                    print(uploads)
                    for item in uploads:
                        if uploads[item]['status'] is not 'UPLOADED':
                            print(uploads[item])
                            self.session.headers.update({'Content-Length': uploads[item]['size']})
                            filename = r'/home/rhemmers/OVA/tmp/{}'.format(uploads[item]['name'])

                            # Since we're using PUT to transfer a large file, don't read the file into
                            # memory, pass the file as the dataDon't
                            vmdk_file = open(filename, 'rb')
                            response = self.session.put(uploads[item]['url'], data=vmdk_file)

                            # Monitor the progress of the upload
                            self.session.headers.update({'Content-Type': 'application/vnd.vmware.vcloud.vAppTemplate+xml'})
                            if 'Content-Length' in self.session.headers:
                                self.session.headers.pop('Content-Length')

                            print('GET: {}'.format(vapp_template_url))

                            # Use a progress bar to show progress of upload
                            progress = int(self.get_upload_progress(vapp_template_url))
                            with progressbar.ProgressBar(max_value=100) as bar_obj:
                                while progress < 100:
                                    time.sleep(2)
                                    progress = int(self.get_upload_progress(vapp_template_url))
                                    bar_obj.update(progress)
                    break
        return 0

    def get_upload_progress(self, href):
        """Get the list of links for the specified catalog.
        """
        response = self.session.get(href)
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for element in root:
                for all_tags in element.findall('.//'):
                    if str(all_tags.tag).endswith('Progress'):
                        return all_tags.text
        return 0

    def get_upload_progress_from_response(self, response):
        """Get the list of links for the specified catalog.
        """
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for element in root:
                for all_tags in element.findall('.//'):
                    if str(all_tags.tag).endswith('Progress'):
                        return all_tags.text
        return 0

    def list_org_catalog(self, catalog):
        """Get the list of links for the specified catalog.
        """
        retval = []
        response = self.session.get(catalog['href'])
        if response.status_code == 200:
            root = ET.fromstring(str(response.text))
            for child in root:
                if child.attrib:
                    retval.append(child.attrib)
        return retval
