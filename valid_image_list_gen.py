import argparse
import json
import os


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

S = set()
for subset in ['val', 'test', 'eval']:
    filename = os.path.join(annotation_dir, "{}-annotations-bbox.json".format(subset))
    with open(filename, "r") as read_file:
        data = json.load(read_file)
    for img in data["images"]:
        S.add(img["id"])
    print(subset, 'done')

with open(os.path.join(annotation_dir, "valid_images.txt"), "w") as f:
    for t in sorted(list(S)):
        f.write(t + "\n")
