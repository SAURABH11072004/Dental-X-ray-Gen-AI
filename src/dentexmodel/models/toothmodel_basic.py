"""
Minimal model code for training and inference
Andreas Werdich
Center for Computational Biomedicine
Harvard Medical School
"""

import logging
from typing import Any

# Pytorch imports
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.models import resnet50, ResNet50_Weights

# Lightning module
from lightning.pytorch import LightningModule
from lightning.pytorch.utilities.types import TRAIN_DATALOADERS, OptimizerLRScheduler, STEP_OUTPUT

logger = logging.getLogger(name=__name__)
torch.set_float32_matmul_precision(precision='high')


class ResNet50Model:
    """

    Class: ResNet50Model

    A class representing a ResNet-50 model with customizable number of outputs.

    Methods: - __init__(self, n_outputs=4): Initializes a new instance of the ResNet50Model class with the specified
    number of outputs. - create_model(self): Creates and returns a ResNet-50 model with the specified number of outputs.

    """
    def __init__(self, n_outputs=4):
        self.n_outputs = n_outputs

    def create_model(self):
        model = resnet50(weights=ResNet50_Weights.DEFAULT)
        model.fc = nn.Sequential(
            nn.Linear(in_features=model.fc.in_features, out_features=512),
            nn.ReLU(),
            nn.Linear(in_features=512, out_features=self.n_outputs)
        )
        return model


class ToothModel(LightningModule):
    """
    ToothModel

    This class represents a PyTorch Lightning module for training and predicting tooth models.

    Attributes:
        train_dataset (Dataset): The training dataset.
        batch_size (int): The batch size for data loading.
        num_workers (int, optional): The number of workers for data loading. Defaults to 1.
        lr (float, optional): The learning rate for the optimizer. Defaults to 1.0e-3.
        model (nn.Module, optional): The pre-trained model. Defaults to None.
        decimals (int): The number of decimal places to round floating point numbers to.

    Methods:
        train_dataloader() -> TRAIN_DATALOADERS:
            Returns the training dataloader for the module.

        forward(x, *args: Any, **kwargs: Any) -> Any:
            Performs a forward pass through the model.

        training_step(batch, batch_idx, *args: Any, **kwargs: Any) -> STEP_OUTPUT:
            Performs a training step on a batch of data.

        predict_step(batch, batch_idx, *args: Any, **kwargs: Any) -> Any:
            Performs a prediction step on a batch of data.

        configure_optimizers() -> OptimizerLRScheduler:
            Configures the optimizer and learning rate scheduler for training.

    """
    def __init__(self,
                 train_dataset,
                 batch_size,
                 num_workers=1,
                 lr=1.0e-3,
                 model=None):
        super().__init__()
        self.save_hyperparameters(ignore=['model'])
        self.train_dataset = train_dataset
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.lr = lr
        self.decimals = 5
        # Model architecture
        if model is None:
            self.model = ResNet50Model().create_model()
        else:
            self.model = model
        # Loss function
        self.criterion = nn.CrossEntropyLoss()

    def train_dataloader(self) -> TRAIN_DATALOADERS:
        dl = DataLoader(self.train_dataset,
                        batch_size=self.batch_size,
                        num_workers=self.num_workers,
                        shuffle=True,
                        pin_memory=True)
        return dl

    def forward(self, x, *args: Any, **kwargs: Any) -> Any:
        x = self.model(x)
        return x

    def training_step(self, batch, batch_idx, *args: Any, **kwargs: Any) -> STEP_OUTPUT:
        image, label = batch
        pred = self.forward(image)
        loss = self.criterion(pred, label)
        return loss

    def predict_step(self, batch, batch_idx, *args: Any, **kwargs: Any) -> Any:
        image, label = batch
        output = self.forward(image)
        return output

    def configure_optimizers(self) -> OptimizerLRScheduler:
        opt = torch.optim.AdamW(self.parameters(), lr=self.lr)
        return opt
