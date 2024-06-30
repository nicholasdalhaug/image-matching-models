
import logging
from pathlib import Path
import numpy as np
import torch

logger = logging.getLogger()
logger.setLevel(31)  # Avoid printing useless low-level logs


def get_image_pairs_paths(inputs):
    inputs = Path(inputs)
    if not inputs.exists():
        raise RuntimeError(f'{inputs} does not exist')
    
    if inputs.is_file():
        with open(inputs) as file:
            lines = file.read().splitlines()
        pairs_of_paths = [l.strip().split(' ') for l in lines]
        for pair in pairs_of_paths:
            if len(pair) != 2:
                raise RuntimeError(f'{pair} should be a pair of paths')
        pairs_of_paths = [(Path(path0.strip()), Path(path1.strip())) for path0, path1 in pairs_of_paths]
    else:
        pair_dirs = sorted(Path(inputs).glob('*'))
        pairs_of_paths = [list(pair_dir.glob('*')) for pair_dir in pair_dirs]
        for pair in pairs_of_paths:
            if len(pair) != 2:
                raise RuntimeError(f'{pair} should be a pair of paths')
    return pairs_of_paths

def to_numpy(x: torch.Tensor | np.ndarray | dict | list) -> np.ndarray:
    """convert item or container of items to numpy

    Args:
        x (torch.Tensor | np.ndarray | dict | list): input

    Returns:
        np.ndarray: numpy array of input
    """
    if isinstance(x, list):
        return np.array([to_numpy(i) for i in x])
    if isinstance(x, dict):
        for k, v in x.items():
            x[k] = to_numpy(v)
    if isinstance(x, torch.Tensor):
        return x.cpu().numpy()
    if isinstance(x, np.ndarray):
        return x

def to_normalized_coords(pts: np.ndarray | torch.Tensor, height: int, width: int):
    """normalize kpt coords from px space to [0,1]
    Assumes pts are in x, y order in array/tensor shape (N, 2)

    Args:
        pts (np.ndarray | torch.Tensor): array of kpts, must be shape (N, 2)
        height (int): height of img 
        width (int): width of img

    Returns:
        np.array: kpts in normalized [0,1] coords
    """
    # normalize kpt coords from px space to [0,1]
    # assume pts are in x,y order
    assert pts.shape[-1] == 2, f'input to `to_normalized_coords` should be shape (N, 2), input is shape {pts.shape}'
    pts = to_numpy(pts).astype(float)
    pts[:, 0] /= width
    pts[:, 1] /= height
    
    return pts

    
def to_px_coords(pts: np.ndarray | torch.Tensor, height: int, width: int) -> np.ndarray:
    """unnormalized kpt coords from [0,1] to px space
    Assumes pts are in x, y order

    Args:
        pts (np.ndarray | torch.Tensor): array of kpts, must be shape (N, 2)
        height (int): height of img 
        width (int): width of img

    Returns:
        np.array: kpts in normalized [0,1] coords
    """
    assert pts.shape[-1] == 2, f'input to `to_px_coords` should be shape (N, 2), input is shape {pts.shape}'
    pts = to_numpy(pts)
    pts[:, 0] *= width
    pts[:, 1] *= height
    
    return pts
