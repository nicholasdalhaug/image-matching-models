
import urllib.request

import sys
from pathlib import Path
import math
import torch
import os
import torchvision.transforms as tfm
import torch.nn.functional as F

sys.path.append(str(Path('third_party/duster')))
from dust3r.inference import inference, load_model
from dust3r.image_pairs import make_pairs
from dust3r.cloud_opt import global_aligner, GlobalAlignerMode
from dust3r.utils.geometry import find_reciprocal_matches, xy_grid

from matching.base_matcher import BaseMatcher


class DusterMatcher(BaseMatcher):
    model_path = 'model_weights/duster_vit_large.pth'    
    vit_patch_size = 16

    def __init__(self, device="cpu", *args, **kwargs):
        super().__init__(device)
        self.normalize = tfm.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))

        self.download_weights()
        self.model = load_model(self.model_path, device)

    @staticmethod
    def download_weights():
        url = 'https://download.europe.naverlabs.com/ComputerVision/DUSt3R/DUSt3R_ViTLarge_BaseDecoder_512_dpt.pth'

        os.makedirs("model_weights", exist_ok=True)
        if not os.path.isfile(DusterMatcher.model_path):
            print("Downloading Duster(ViT large)... (takes a while)")
            urllib.request.urlretrieve(url, DusterMatcher.model_path)

    def preprocess(self, img):
        # the super-class already makes sure that img0,img1 have 
        # same resolution and that h == w
        _, h, _ = img.shape
        imsize = h
        if not ((h % self.vit_patch_size) == 0):
            imsize = int(self.vit_patch_size*round(h / self.vit_patch_size, 0))            
            img = tfm.functional.resize(img, imsize, antialias=True)
        img = self.normalize(img).unsqueeze(0)

        return img

    def _forward(self, img0, img1):
        
        img0 = self.preprocess(img0)
        img1 = self.preprocess(img1)

        images = [{'img': img0, 'idx': 0, 'instance': 0}, {'img': img1, 'idx': 1, 'instance': 1}]
        pairs = make_pairs(images, scene_graph='complete', prefilter=None, symmetrize=True)
        output = inference(pairs, self.model, self.device, batch_size=1)

        scene = global_aligner(output, device=self.device, mode=GlobalAlignerMode.PairViewer)
        # retrieve useful values from scene:
        confidence_masks = scene.get_masks()
        pts3d = scene.get_pts3d()
        imgs = scene.imgs
        pts2d_list, pts3d_list = [], []
        for i in range(2):
            conf_i = confidence_masks[i].cpu().numpy()
            pts2d_list.append(xy_grid(*imgs[i].shape[:2][::-1])[conf_i])  # imgs[i].shape[:2] = (H, W)
            pts3d_list.append(pts3d[i].detach().cpu().numpy()[conf_i])
        reciprocal_in_P2, nn2_in_P1, _ = find_reciprocal_matches(*pts3d_list)

        mkpts0 = pts2d_list[1][reciprocal_in_P2]
        mkpts1 = pts2d_list[0][nn2_in_P1][reciprocal_in_P2]

        # process_matches is implemented by the parent BaseMatcher, it is the
        # same for all methods, given the matched keypoints
        return self.process_matches(mkpts0, mkpts1)
