"""vCloud Director APIs for media (iso/ova) upload.

Usage:
   Upload ISO: $ python ovfs.py -c <catalog name> -o <org name> -u media -f <path to ISO>
   Upload OVF: $ python ovfs.py -c <catalog name> -o <org name> -u ovf -f <path to OVA>

"""
import argparse
import os
import logging
import pprint
import progressbar
import requests
import sys
import time

from vcloud_director import VCloudDirector

requests.packages.urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(name)s %(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--show', '-s', action='store_true', help='show list of orgs', required=False)
    parser.add_argument('--list', '-l', action='store_true', help='show list of Org\'s catalogs', required=False)
    parser.add_argument('--upload', '-u', type=str, help='upload file', choices=['media', 'ovf'], required=False)
    parser.add_argument('--org', '-o', type=str, help='org name', required=False)
    parser.add_argument('--catalog', '-c', type=str, help='catalog name', required=False)
    parser.add_argument('--file', '-f', type=str, help='file name', required=False)

    args = parser.parse_args()

    if not args.list and not args.upload and not args.show:
        parser.print_help()
        sys.exit()

    client = VCloudDirector()

    pp = pprint.PrettyPrinter(indent=4)

    org_list = client.list_orgs()

    # List the orgs found in vCloud Director
    if args.show:
        logger.info('---------- List of Orgs ----------')
        for org in org_list:
            logger.info('Org Name: {:20s}  URL: {}'.format(org['name'], org['href']))

    # List the items found in the Org's catalog
    if args.list:
        if not args.org:
            logger.error('ERROR: missing Org name (-o)')
            sys.exit()

        logger.info('---------- Org: {}  Catalog: {} ----------'.format(args.org, args.catalog))
        for org in org_list:
            if org['name'] == args.org:
                print('Org Name: {}'.format(org['name']))
                links = client.list_org_links(org)

                for link in links:
                    if 'catalog' in link['type']:
                        logger.info('\tCatalog: ' + str(link['name']))
                        catalogs = client.list_org_catalog_links(link)
                        for template in catalogs:
                            logger.info('\t\t{}'.format(template))

    # Obtain the URL of the target catalog that will receive the media upload
    if args.upload:
        if not args.catalog or not args.file:
            print('ERROR: catalog name (-c) or file name (-f) not specified parameter')
            sys.exit()

        try:
            filesize = os.path.getsize(args.file)
        except OSError as err:
            print('ERROR: File \'{}\' does not exist'.format(args.file))
            sys.exit()

        for org in org_list:
            if org['name'] == args.org:
                print('Org Name: {}'.format(org['name']))
                links = client.list_org_links(org)

                for link in links:
                    if link.get('name') == args.catalog:
                        if 'application/vnd.vmware.vcloud.catalog+xml' == link['type']:
                            if args.upload == 'media':
                                tagtype = r'application/vnd.vmware.vcloud.media+xml'
                            else:
                                tagtype = r'application/vnd.vmware.vcloud.uploadVAppTemplateParams+xml'

                            print('  Catalog: ' + str(link['name']))
                            catalogs = client.get_upload_catalog_links(link, tagtype)

                            for catalog in catalogs:
                                print('    Link: {}'.format(str(catalog)))
                                # Upload iso media to catalog
                                if args.upload == 'media':
                                    href = client.upload_media(catalog, args.file, filesize, 'ISO database image')

                                    # Use progress bar to show progress of upload
                                    progress = int(client.get_upload_progress(href))
                                    with progressbar.ProgressBar(max_value=100) as bar:
                                        while progress < 100:
                                            time.sleep(0.5)
                                            progress = int(client.get_upload_progress(href))
                                            bar.update(progress)
                                else:
                                    href = client.upload_template(catalog, args.file, 'API vApp Template', 'My vApp Template')

    client.logout()
