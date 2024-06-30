from matching.base_matcher import BaseMatcher
from matching.utils import to_numpy
import torch
from pathlib import Path
import gdown
import sys
from copy import deepcopy
import torchvision.transforms as tfm

sys.path.append(str(Path(__file__).parent.parent.joinpath('third_party/EfficientLoFTR')))

from src.loftr import LoFTR, full_default_cfg, opt_default_cfg, reparameter
from matching import WEIGHTS_DIR

class EfficientLoFTRMatcher(BaseMatcher):
    weights_src = 'https://drive.google.com/file/d/1jFy2JbMKlIp82541TakhQPaoyB5qDeic/view'
    model_path = WEIGHTS_DIR.joinpath('eloftr_outdoor.ckpt')
    divisible_size = 32
    
    def __init__(self, device="cpu", cfg='full', **kwargs):
        super().__init__(device, **kwargs)
        
        self.precision = kwargs.get('precision', self.get_precision())
        
        self.download_weights()
        
        self.matcher = LoFTR(config=deepcopy(full_default_cfg if cfg =='full' else opt_default_cfg))
        
        self.matcher.load_state_dict(torch.load(self.model_path, map_location=torch.device('cpu'))['state_dict'])
        self.matcher = reparameter(self.matcher).to(self.device).eval()
       
    def get_precision(self):
        return 'fp16'
     
    def download_weights(self):
        if not Path(EfficientLoFTRMatcher.model_path).is_file():
            print("Downloading eLoFTR outdoor... (takes a while)")
            gdown.download(EfficientLoFTRMatcher.weights_src,
                                output=str(EfficientLoFTRMatcher.model_path),
                                fuzzy=True)

    def preprocess(self, img):
        _, h, w = img.shape
        orig_shape = h, w
        imsize = h
        if not ((h % EfficientLoFTRMatcher.divisible_size) == 0):
            imsize = int(EfficientLoFTRMatcher.divisible_size*round(h / EfficientLoFTRMatcher.divisible_size, 0))
            img = tfm.functional.resize(img, imsize, antialias=True)
        _, new_h, new_w = img.shape
        if not ((new_w % EfficientLoFTRMatcher.divisible_size) == 0):
            safe_w = int(EfficientLoFTRMatcher.divisible_size*round(new_w / EfficientLoFTRMatcher.divisible_size, 0))
            img = tfm.functional.resize(img, (new_h, safe_w), antialias=True)
            
        return tfm.Grayscale()(img).unsqueeze(0).to(self.device), orig_shape
        
    def _forward(self, img0, img1):
        img0, img0_orig_shape = self.preprocess(img0)
        img1, img1_orig_shape = self.preprocess(img1)

        batch = {'image0': img0, 'image1': img1}
        if self.precision == 'mp' and self.device == 'cuda':
            with torch.autocast(enabled=True, device_type='cuda'):
                self.matcher(batch)
        else:
            self.matcher(batch)
            
        mkpts0 = to_numpy(batch['mkpts0_f'])
        mkpts1 = to_numpy(batch['mkpts1_f'])
        
        H0, W0, H1, W1 = *img0.shape[-2:], *img1.shape[-2:] 
        mkpts0 = self.rescale_coords(mkpts0, *img0_orig_shape, H0, W0)
        mkpts1 = self.rescale_coords(mkpts1, *img1_orig_shape, H1, W1)

        
        num_inliers, H, inliers0, inliers1 = self.process_matches(mkpts0, mkpts1)
        return {'num_inliers':num_inliers,
                'H': H,
                'mkpts0':mkpts0, 'mkpts1':mkpts1,
                'inliers0':inliers0, 'inliers1':inliers1,
                'kpts0':None, 'kpts1':None, 
                'desc0':None,'desc1': None}
     