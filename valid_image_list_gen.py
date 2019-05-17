import argparse
import json
import os
import sys


def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(description='Detect valid images from image jsons')
    parser.add_argument('-p', dest='path',
                        help='path to openimages data',
                        type=str)
    args = parser.parse_args()
    return args


args = parse_args()
data_dir = args.path
annotation_dir = os.path.join(data_dir, 'annotations')

S = dict()
for subset in ['val', 'test', 'train']:
    filename = os.path.join(annotation_dir, "{}-annotations-bbox.json".format(subset))
    with open(filename, "r") as read_file:
        data = json.load(read_file)
    for img in data["images"]:
        S[img["id"]] = (img["width"], img["height"])
    print(subset, 'done')
    sys.stdout.flush()

with open(os.path.join(annotation_dir, "valid_images.csv"), "w") as f:
    for i, t in enumerate(sorted(S.keys())):
        f.write("%s,%d,%d\n" % (t, S[t][0], S[t][1]))
