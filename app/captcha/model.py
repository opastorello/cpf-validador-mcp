import torch.nn as nn

CHARSET = "0123456789abcdefghijklmnopqrstuvwxyz"  # 36 chars
BLANK = len(CHARSET)  # CTC blank token = 36
NUM_CLASSES = len(CHARSET) + 1  # 37

IMG_H = 60
IMG_W = 160


class CaptchaModel(nn.Module):
    def __init__(self):
        super().__init__()
        # CNN backbone: input (B, 1, 60, 160)
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2, 2),    # -> (B,32,30,80)
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2, 2),   # -> (B,64,15,40)
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d((3,1)), # -> (B,128,5,40)
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(), nn.MaxPool2d((5,1)), # -> (B,256,1,40)
        )
        # Reshape: (B, 256, 1, 40) -> (40, B, 256) for LSTM
        self.lstm = nn.LSTM(256, 128, num_layers=2, bidirectional=True, batch_first=False, dropout=0.1)
        self.fc = nn.Linear(256, NUM_CLASSES)  # 128*2 bidirectional

    def forward(self, x):
        # x: (B, 1, H, W)
        features = self.cnn(x)  # (B, 256, 1, W')
        B, C, H, W = features.shape
        features = features.squeeze(2)  # (B, 256, W')
        features = features.permute(2, 0, 1)  # (W', B, 256)
        out, _ = self.lstm(features)  # (W', B, 256)
        out = self.fc(out)  # (W', B, NUM_CLASSES)
        return out  # log_softmax applied in loss


def decode_greedy(output):
    """CTC greedy decode. output: (T, B, C) after softmax. Returns list of strings."""
    output = output.argmax(dim=2)  # (T, B)
    results = []
    for b in range(output.shape[1]):
        seq = output[:, b].tolist()
        # collapse repeats and remove blank
        chars = []
        prev = None
        for c in seq:
            if c != prev:
                if c != BLANK:
                    chars.append(CHARSET[c])
                prev = c
        results.append("".join(chars))
    return results
