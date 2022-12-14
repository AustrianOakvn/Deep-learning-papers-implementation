import torch
import torch.nn as nn
from utils import intersection_over_union


class YoloLoss(nn.Module):
    def __init__(self, S=7, B=2, C=20) -> None:
        super(YoloLoss, self).__init__()
        self.mse = nn.MSELoss(reduction="sum")
        self.S = S
        self.B = B
        self.C = C
        self.lambda_noobj = 0.5
        self.lambda_coord = 5

    def forward(self, predictions, target):
        # prediction (N, S, S, 30)
        predictions = predictions.reshape(-1, self.S, self.S, self.C + self.B*5)

        # prediction last dim: C_1, ..., C_20, p_1, x_1, y_1, w_1, h_1, p_2, x_2, y_2, w_2, h_2
        iou_b1 = intersection_over_union(predictions[..., 21:25], target[..., 21:25])
        iou_b2 = intersection_over_union(predictions[..., 26:30], target[..., 21:25])

        ious = torch.cat([iou_b1.unsqueeze(0), iou_b2.unsqueeze(0)], dim=0)
        iou_maxes, bestbox = torch.max(ious, dim=0)

        # identity of object 0 or 1
        exists_box = target[..., 20].unsqueeze(3)
        
        
        ########################
        # Box coordinates Loss #
        ########################
        
        box_predictions = exists_box*(bestbox*predictions[..., 26:30]+(1-bestbox)*predictions[..., 21:25])

        box_targets = exists_box*target[..., 21:25]

        # Calculate the loss for weight and height
        box_predictions[..., 2:4] = torch.sign(box_predictions[..., 2:4])*torch.sqrt(torch.abs(box_predictions[..., 2:4]+1e-6))

        box_targets[..., 2:4] = torch.sqrt(box_targets[..., 2:4])

        box_loss = self.mse(torch.flatten(box_predictions, end_dim=2),
                            torch.flatten(box_targets, end_dim=-2))

        ###############
        # Object Loss #
        ###############

        pred_box = (bestbox*predictions[..., 25:26] + (1-bestbox)*predictions[..., 20:21])

        object_loss = self.mse(torch.flatten(exists_box*pred_box),
                               torch.flatten(exists_box*target[..., 20:21]))

        ##################
        # No object Loss #
        ##################

        no_object_loss = self.mse(torch.flatten((1-exists_box)*predictions[..., 20:21], start_dim=1),
                                torch.flatten((1-exists_box)*target[..., 20:21], start_dim=1))

        no_object_loss += self.mse(torch.flatten((1-exists_box)*predictions[..., 25:26], start_dim=1),
                        torch.flatten((1-exists_box)*target[..., 20:21], start_dim=1))

        ##############
        # Class Loss #
        ##############

        class_loss = self.mse(torch.flatten(exists_box*predictions[..., :20], end_dim=-2),
                                torch.flatten(exists_box*target[..., :20], end_dim=-2))

        loss = (self.lambda_coord*box_loss 
                + object_loss 
                + self.lambda_noobj*no_object_loss
                + class_loss)

