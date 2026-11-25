import torch.nn as nn
import timm


def build_vit(num_classes=1000, pretrained=True, name="deit_tiny_patch16_224"):
    model = timm.create_model(name, pretrained=pretrained, num_classes=num_classes)
    for m in model.modules():
        if isinstance(m, nn.GELU):
            m.approximate = "tanh"
    return model


if __name__ == "__main__":
    import torch
    m = build_vit(pretrained=False).eval()
    n = sum(p.numel() for p in m.parameters()) / 1e6
    y = m(torch.randn(1, 3, 224, 224))
    print(f"deit_tiny params {n:.2f}M out {tuple(y.shape)}")
