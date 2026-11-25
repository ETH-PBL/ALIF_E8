import os
import time
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from model import build_vit

MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]


def loaders(data_dir, batch):
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    val_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    tr = datasets.ImageFolder(os.path.join(data_dir, "train"), train_tf)
    va = datasets.ImageFolder(os.path.join(data_dir, "val"), val_tf)
    tl = DataLoader(tr, batch_size=batch, shuffle=True, num_workers=6, pin_memory=True, drop_last=True)
    vl = DataLoader(va, batch_size=batch, shuffle=False, num_workers=3, pin_memory=True)
    return tl, vl, tr.classes


@torch.no_grad()
def accuracy(model, loader, dev):
    model.eval()
    correct = 0
    total = 0
    for x, y in loader:
        x = x.to(dev)
        y = y.to(dev)
        pred = model(x).argmax(1)
        correct += (pred == y).sum().item()
        total += y.numel()
    return correct / max(total, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--pretrained", type=int, default=1)
    ap.add_argument("--out", default="runs/vit")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    tl, vl, classes = loaders(args.data_dir, args.batch)
    print(f"train {len(tl.dataset)} val {len(vl.dataset)} classes {len(classes)}", flush=True)
    with open(os.path.join(args.out, "labels.txt"), "w") as f:
        f.write("\n".join(classes) + "\n")

    model = build_vit(num_classes=len(classes), pretrained=bool(args.pretrained)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    crit = nn.CrossEntropyLoss()
    best = 0.0
    for ep in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        run = 0.0
        for it, (x, y) in enumerate(tl):
            x = x.to(dev, non_blocking=True)
            y = y.to(dev, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            loss = crit(model(x), y)
            loss.backward()
            opt.step()
            run += loss.item()
            if it % 50 == 0:
                print(f"  ep{ep} it{it}/{len(tl)} loss {loss.item():.3f}", flush=True)
        sched.step()
        acc = accuracy(model, vl, dev)
        print(f"[ep{ep}] loss {run/len(tl):.3f} val_acc {acc:.4f} {time.time()-t0:.0f}s", flush=True)
        torch.save({"model": model.state_dict(), "classes": classes, "acc": acc}, os.path.join(args.out, "vit_last.pt"))
        if acc > best:
            best = acc
            torch.save({"model": model.state_dict(), "classes": classes, "acc": acc}, os.path.join(args.out, "vit_best.pt"))
            print(f"  new best acc {best:.4f}", flush=True)
    print(f"DONE best val_acc {best:.4f}", flush=True)


if __name__ == "__main__":
    main()
