"""
Create PyTorch data set from data frames
Andreas Werdich
Center for Computational Biomedicine
"""

import numpy as np
import logging
import torch
from torch.utils.data import Dataset
import albumentations as alb
import cv2
from albumentations.augmentations.geometric.resize import LongestMaxSize
from albumentations.augmentations.geometric.transforms import PadIfNeeded

# Imports from this module
from dentexmodel.imageproc import ImageData, validate_image_data

logger = logging.getLogger(name=__name__)


def load_and_process_image(image_file_path, max_image_size=550):
    """
    Image preprocessing
    """
    # For the albumentations transformation, max_image_size needs to be of type 'int'
    if not isinstance(max_image_size, int):
        max_image_size = int(max_image_size)
    transform = alb.Compose([LongestMaxSize(max_size=max_image_size),
                             PadIfNeeded(min_height=max_image_size,
                                         min_width=max_image_size,
                                         border_mode=cv2.BORDER_CONSTANT,
                                         value=0)])
    im_raw = ImageData().load_image(image_file_path)
    im_output = transform(image=im_raw)['image']
    return im_output


class DatasetFromDF(Dataset):
    """
    Creates a PyTorch dataset from a data frame
    """

    def __init__(self,
                 data,
                 file_col,
                 label_col,
                 max_image_size,
                 transform=None,
                 validate=False):
        """
        Attributes:
        data (pd.DataFrame):    file paths and labels
        file_col (str):         column name for file paths
        label_col (str):        column name for corresponding labels
        max_image_size (int):   Resize and square pad all images to this size
        transform     (alb):     transformation object
        verify        (bool):    load and verify all images on instantiation
        """
        self.df = data
        self.file_col = file_col
        self.label_col = label_col
        self.max_image_size = max_image_size
        self.transform = transform
        self.validate = validate
        if self.validate:
            validate_image_data(data_df=self.df, file_path_col=self.file_col)

    def __len__(self):
        return self.df.shape[0]

    def __getitem__(self, idx):
        idx = idx % self.__len__()
        df_idx = self.df.iloc[idx]
        file, label = df_idx[self.file_col], df_idx[self.label_col]
        assert isinstance(label, np.int64), f'Label must be type np.int64.'
        # Image preprocessing, e.g., color conversion
        img = load_and_process_image(image_file_path=file, max_image_size=self.max_image_size)
        if self.transform:
            img = self.transform(image=img)['image']
        img_tensor = torch.from_numpy(img).permute(2, 0, 1)
        # For grayscale images, we need to add a color dimension.
        # img_tensor = torch.unsqueeze(img_tensor, dim=0)
        # img_tensor = img_tensor.permute(2, 0, 1)
        label_tensor = torch.from_numpy(np.array(label))
        output = tuple([img_tensor, label_tensor])
        return output
