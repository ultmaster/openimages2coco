import multiprocessing

import matplotlib

matplotlib.use('Agg')

import os
import sys
import csv
import json
import time
import numpy as np
import skimage.io as io
from openimages import OpenImages


def _url_to_license(licenses, mode='http'):
    # create dict with license urls as 
    # mode is either http or https

    # create dict
    licenses_by_url = {}

    for license in licenses:
        # Get URL
        if mode == 'https':
            url = 'https:' + license['url'][5:]
        else:
            url = license['url']
        # Add to dict
        licenses_by_url[url] = license

    return licenses_by_url


def convert_category_annotations(original_category_info):
    categories = []
    num_categories = len(original_category_info)
    for i in range(num_categories):
        cat = {}
        cat['id'] = i + 1
        cat['name'] = original_category_info[i][1]
        cat['original_id'] = original_category_info[i][0]

        categories.append(cat)

    return categories


def _convert_image_annotation_chunk(original_image_metadata, image_dir, licenses, verbose, idx):
    # Get dict with license urls
    licenses_by_url_http = _url_to_license(licenses, mode='http')
    licenses_by_url_https = _url_to_license(licenses, mode='https')
    # Create list
    images = []
    # Set starting time
    start_time = time.time()
    print("Running on chunk %d" % idx)
    sys.stdout.flush()

    # loop through entries skipping title line
    num_images = len(original_image_metadata)
    for i in range(0, num_images):
        # Print status info
        if verbose > 0:
            if i % 10 == 0:
                elapsed_time = time.time() - start_time
                elapsed_hours = elapsed_time // 3600
                elapsed_mins = (elapsed_time % 3600) // 60
                total_time = elapsed_time * num_images / (i + 1)
                total_hours = total_time // 3600
                total_mins = (total_time % 3600) // 60
                print('Image {}/{} Time: {:.0f}h {:.0f}min / {:.0f}h {:.0f}min'.format(i, num_images - 1,
                                                                                       elapsed_hours, elapsed_mins,
                                                                                       total_hours, total_mins),
                      end='\r')
                sys.stdout.flush()

        # Select image ID as key
        key = original_image_metadata[i][0]

        # Copy information
        img = {}
        img['id'] = key
        img['file_name'] = key + '.jpg'
        img['original_url'] = original_image_metadata[i][2]
        license_url = original_image_metadata[i][4]
        # Look up license id
        try:
            img['license'] = licenses_by_url_https[license_url]['id']
        except:
            img['license'] = licenses_by_url_http[license_url]['id']

        # Load image to extract height and width
        filename = os.path.join(image_dir, img['file_name'])
        try:
            img_data = io.imread(filename)
        except:
            continue

        # catch weird image file type
        if len(img_data.shape) < 2:
            img['height'] = img_data[0].shape[0]
            img['width'] = img_data[0].shape[1]
        else:
            img['height'] = img_data.shape[0]
            img['width'] = img_data.shape[1]

        # Add to list of images
        images.append(img)

    return images


def chunk_helper(image_file_list, image_dir, licenses, verbose, idx):
    return _convert_image_annotation_chunk(image_file_list, image_dir, licenses, verbose, idx)


def convert_image_annotations(original_image_metadata, image_dir, licenses, mode='parallel', verbose=1):
    # Enclosing function of _convert_image_annotation_chunk to make it parallelizable
    # in parallel mode:
    # verbose: 0 = no status info, 1 = some progress info, 50 = info for every finished chunk
    # in feed-forward mode:
    # verbose: 0 = no status info, 1 = progress info every 10 images

    if mode == 'parallel':
        N = 10000  # chunk size
        chunks = []
        for i in range(0, len(original_image_metadata), N):
            chunks.append(original_image_metadata[i:i + N])
        print("Total: %d chunks" % len(chunks))

        with multiprocessing.Pool(64) as pool:
            images_in_chunks = pool.starmap(chunk_helper, [(c, image_dir, licenses, 0, i) for i, c in enumerate(chunks)])
        images = [chunk[i] for chunk in images_in_chunks for i in range(len(chunk))]

    else:
        images = _convert_image_annotation_chunk(original_image_metadata, image_dir, licenses, verbose=verbose, idx=0)

    return images


def _image_list_to_dict(images):
    # Helper function to create dict of images by image id 
    # modelled from the cocoapi
    imgs = {}
    for img in images:
        imgs[img['id']] = img

    return imgs


def _category_list_to_dict(categories):
    # Helper function to create dict of categories by integer category id
    # modelled from the cocoapi
    cats = {}
    for cat in categories:
        cats[cat['id']] = cat

    return cats


def _categories_by_original_ids(cats):
    # Helperfunction to create dict mapping original utf8 category ids to categories
    origCats = {}
    for i in cats.keys():
        key = cats[i]['original_id']
        origCats[key] = cats[i]

    return origCats


def convert_instance_annotations(original_annotations, images, categories, start_index=0):
    imgs = _image_list_to_dict(images)
    cats = _category_list_to_dict(categories)
    orig_cats = _categories_by_original_ids(cats)

    annotations = []

    num_instances = len(original_annotations)
    for i in range(0, num_instances):
        # print progress
        if i % 5000 == 0:
            print('{}/{} annotations processed'.format(i, num_instances - 1))
            sys.stdout.flush()
        # set individual instance id
        # use start_index to separate indices between dataset splits
        key = i + start_index
        csv_line = i
        ann = {}
        ann['id'] = key
        image_id = original_annotations[csv_line][0]
        ann['image_id'] = image_id
        if image_id not in imgs:
            continue
        ann['original_category_id'] = original_annotations[csv_line][2]
        ann['category_id'] = orig_cats[original_annotations[csv_line][2]]['id']
        x = float(original_annotations[csv_line][4]) * imgs[image_id]['width']
        y = float(original_annotations[csv_line][6]) * imgs[image_id]['height']
        dx = (float(original_annotations[csv_line][5]) - float(original_annotations[csv_line][4])) * imgs[image_id][
            'width']
        dy = (float(original_annotations[csv_line][7]) - float(original_annotations[csv_line][6])) * imgs[image_id][
            'height']

        ann['bbox'] = [round(a, 2) for a in [x, y, dx, dy]]
        ann['area'] = round(dx * dy, 2)
        ann['isoccluded'] = int(original_annotations[csv_line][8])
        ann['istruncated'] = int(original_annotations[csv_line][9])
        ann['iscrowd'] = int(original_annotations[csv_line][10])
        ann['isdepiction'] = int(original_annotations[csv_line][11])
        ann['isinside'] = int(original_annotations[csv_line][12])
        annotations.append(ann)

    return annotations


def convert_openimages_subset(annotation_dir, image_dir, subset, return_data=False):
    # Select correct source files for each subset
    category_sourcefile = 'class-descriptions-boxable.csv'
    if subset == 'train':
        image_sourcefile = 'train-images-boxable-with-rotation.csv'
        annotation_sourcefile = 'train-annotations-bbox.csv'
    elif subset == 'val':
        image_sourcefile = 'validation-images-with-rotation.csv'
        annotation_sourcefile = 'validation-annotations-bbox.csv'
    elif subset == 'test':
        image_sourcefile = 'test-images-with-rotation.csv'
        annotation_sourcefile = 'test-annotations-bbox.csv'

    # Load original annotations
    print('loading original annotations ...')
    sys.stdout.flush()
    with open('{}/{}'.format(annotation_dir, category_sourcefile), 'r', encoding='utf-8') as f:
        csv_f = csv.reader(f)
        original_category_info = []
        for row in csv_f:
            original_category_info.append(row)
    print("First step done")
    sys.stdout.flush()

    dirty_count, total_count = 0, 0
    with open('{}/{}'.format(annotation_dir, image_sourcefile), 'r', encoding='utf-8') as f:
        csv_f = csv.reader(f)
        original_image_metadata = []
        for i, row in enumerate(csv_f):
            if i == 0: continue
            if i % 10000 == 0:
                print("Source file progress:", i)
                sys.stdout.flush()
            total_count += 1
            if not os.path.exists(os.path.join(image_dir, row[0] + ".jpg")):
                dirty_count += 1
                continue
            original_image_metadata.append(row)
    print("Image sourcefile: %d out of %d dirty" % (dirty_count, total_count))
    sys.stdout.flush()

    dirty_count = total_count = 0
    with open('{}/{}'.format(annotation_dir, annotation_sourcefile), 'r') as f:
        csv_f = csv.reader(f)
        original_annotations = []
        for i, row in enumerate(csv_f):
            if i == 0: continue
            if i % 10000 == 0:
                print("Annotation file progress:", i)
                sys.stdout.flush()
            total_count += 1
            if not os.path.exists(os.path.join(image_dir, row[0] + ".jpg")):
                dirty_count += 1
                continue
            original_annotations.append(row)
    print("Annotation file: %d out of %d dirty" % (dirty_count, total_count))
    print('loading original annotations ... Done')
    sys.stdout.flush()

    # Create dataset class to store annotations
    oi = OpenImages()

    # Add basic dataset info
    print('adding basic dataset info')
    oi.dataset['info'] = {'contributos': 'Krasin I., Duerig T., Alldrin N., \
                          Ferrari V., Abu-El-Haija S., Kuznetsova A., Rom H., \
                          Uijlings J., Popov S., Kamali S., Malloci M., Pont-Tuset J., \
                          Veit A., Belongie S., Gomes V., Gupta A., Sun C., Chechik G., \
                          Cai D., Feng Z., Narayanan D., Murphy K.',
                          'date_announced': '2018/04/30',
                          'description': 'Open Images Dataset v4',
                          'url': 'https://storage.googleapis.com/openimages/web/index.html',
                          'version': '4.0',
                          'year': 2018}

    # Add license information
    print('adding basic license info')
    oi.dataset['licenses'] = [{'id': 1,
                               'name': 'Attribution-NonCommercial-ShareAlike License',
                               'url': 'http://creativecommons.org/licenses/by-nc-sa/2.0/'},
                              {'id': 2,
                               'name': 'Attribution-NonCommercial License',
                               'url': 'http://creativecommons.org/licenses/by-nc/2.0/'},
                              {'id': 3,
                               'name': 'Attribution-NonCommercial-NoDerivs License',
                               'url': 'http://creativecommons.org/licenses/by-nc-nd/2.0/'},
                              {'id': 4,
                               'name': 'Attribution License',
                               'url': 'http://creativecommons.org/licenses/by/2.0/'},
                              {'id': 5,
                               'name': 'Attribution-ShareAlike License',
                               'url': 'http://creativecommons.org/licenses/by-sa/2.0/'},
                              {'id': 6,
                               'name': 'Attribution-NoDerivs License',
                               'url': 'http://creativecommons.org/licenses/by-nd/2.0/'},
                              {'id': 7,
                               'name': 'No known copyright restrictions',
                               'url': 'http://flickr.com/commons/usage/'},
                              {'id': 8,
                               'name': 'United States Government Work',
                               'url': 'http://www.usa.gov/copyright.shtml'}]

    # Convert category information
    print('converting category info')
    oi.dataset['categories'] = convert_category_annotations(original_category_info)

    # Convert image mnetadata
    print('converting image info ...')
    oi.dataset['images'] = convert_image_annotations(original_image_metadata,
                                                     image_dir,
                                                     oi.dataset['licenses'],
                                                     mode='parallel',
                                                     verbose=10)

    # Convert instance annotations
    print('converting annotations ...')
    oi.dataset['annotations'] = convert_instance_annotations(original_annotations,
                                                             oi.dataset['images'],
                                                             oi.dataset['categories'],
                                                             start_index=0)

    # Write annotations into .json file
    filename = "{}/{}-annotations-bbox.json".format(annotation_dir, subset)
    print('writing output to {}'.format(filename))
    sys.stdout.flush()
    with open(filename, "w") as write_file:
        json.dump(oi.dataset, write_file)
    print('Done')
    sys.stdout.flush()

    if return_data:
        return oi
