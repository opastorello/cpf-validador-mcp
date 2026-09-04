import argparse
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from app.captcha.dataset import CaptchaDataset, collate_fn
from app.captcha.model import BLANK, CaptchaModel
from app.captcha.registry import next_version, promote_if_best, save_version

MODEL_PATH = Path(__file__).parent / "captcha_model.pt"
DATA_DIR = Path(__file__).parent / "data"


def decode_greedy_batch(output, dataset):
    """Decode CTC greedy output for a batch."""
    from app.captcha.model import decode_greedy
    return decode_greedy(output)


def evaluate(model, loader, ctc_loss, device):
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    from app.captcha.model import decode_greedy

    with torch.no_grad():
        for imgs, targets_flat, target_lengths in loader:
            imgs = imgs.to(device)
            targets_flat = targets_flat.to(device)
            target_lengths = target_lengths.to(device)

            output = model(imgs)  # (T, B, C)
            T, B, C = output.shape
            output_log = torch.log_softmax(output, dim=2)
            input_lengths = torch.full((B,), T, dtype=torch.long, device=device)

            loss = ctc_loss(output_log, targets_flat, input_lengths, target_lengths)
            total_loss += loss.item()

            preds = decode_greedy(output_log)

            # Reconstruct ground truth strings from targets_flat and target_lengths
            from app.captcha.model import CHARSET
            idx = 0
            for i, length in enumerate(target_lengths.tolist()):
                gt_indices = targets_flat[idx: idx + length].tolist()
                idx += length
                gt_str = "".join(CHARSET[c] for c in gt_indices)
                if preds[i] == gt_str:
                    correct += 1
                total += 1

    avg_loss = total_loss / max(len(loader), 1)
    accuracy = correct / max(total, 1)
    return avg_loss, accuracy


def train(epochs=50, batch_size=32, lr=3e-4, val_split=0.1, n_samples=0, checkpoint=None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    dataset = CaptchaDataset(DATA_DIR, augment=True)
    n_val = max(1, int(len(dataset) * val_split))
    n_train = len(dataset) - n_val
    train_set, val_set = random_split(dataset, [n_train, n_val])

    train_loader = DataLoader(
        train_set,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_fn,
        num_workers=0,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_set,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn,
        num_workers=0,
        pin_memory=True,
    )

    model = CaptchaModel().to(device)
    if checkpoint:
        ckpt = Path(checkpoint)
        if not ckpt.exists():
            print(f"Checkpoint nao encontrado: {ckpt}")
            sys.exit(1)
        model.load_state_dict(torch.load(ckpt, map_location=device))
        print(f"Fine-tuning a partir de: {ckpt}")
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    ctc_loss = nn.CTCLoss(blank=BLANK, zero_infinity=True)
    scaler = torch.amp.GradScaler("cuda") if device.type == "cuda" else None

    best_val_loss = float("inf")
    best_val_acc = 0.0
    no_improve = 0
    version = next_version()
    epochs_at_best = 0
    print(f"Versao: v{version}")

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0

        for imgs, targets_flat, target_lengths in train_loader:
            imgs = imgs.to(device)
            targets_flat = targets_flat.to(device)
            target_lengths = target_lengths.to(device)

            optimizer.zero_grad()

            if scaler is not None:
                with torch.amp.autocast("cuda"):
                    output = model(imgs)  # (T, B, C)
                    T, B, C = output.shape
                    output_log = torch.log_softmax(output, dim=2)
                    input_lengths = torch.full((B,), T, dtype=torch.long, device=device)
                    loss = ctc_loss(output_log, targets_flat, input_lengths, target_lengths)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                output = model(imgs)  # (T, B, C)
                T, B, C = output.shape
                output_log = torch.log_softmax(output, dim=2)
                input_lengths = torch.full((B,), T, dtype=torch.long, device=device)
                loss = ctc_loss(output_log, targets_flat, input_lengths, target_lengths)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()

            train_loss += loss.item()

        scheduler.step()

        avg_train_loss = train_loss / max(len(train_loader), 1)
        val_loss, val_acc = evaluate(model, val_loader, ctc_loss, device)

        print(
            f"Epoch {epoch:3d}/{epochs} | "
            f"train_loss={avg_train_loss:.4f} | "
            f"val_loss={val_loss:.4f} | "
            f"val_accuracy={val_acc:.4f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            epochs_at_best = epoch
            no_improve = 0
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"  -> Saved best model (val_loss={best_val_loss:.4f})")
        else:
            no_improve += 1
            if no_improve >= 20:
                print("Early stopping: no improvement for 10 epochs.")
                break

    version_path = save_version(
        MODEL_PATH,
        version=version,
        val_accuracy=best_val_acc,
        val_loss=best_val_loss,
        epochs_trained=epochs_at_best,
        samples=n_samples,
        batch_size=batch_size,
        lr=lr,
    )
    promoted = promote_if_best(version, best_val_acc)
    status = "ATIVO (melhor geral)" if promoted else "salvo (nao superou o melhor)"
    print(f"Training complete. v{version} | val_acc={best_val_acc:.4f} | val_loss={best_val_loss:.4f} | {status}")
    print(f"Modelo salvo em: {version_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Caminho para um .pt existente para fine-tuning (ex: app/captcha/captcha_model.pt)")
    args = parser.parse_args()
    n = len(CaptchaDataset(DATA_DIR))
    print(f"Dataset: {n} amostras")
    if n < 50:
        print("Minimo 50 amostras necessarias. Rode collector primeiro.")
        sys.exit(1)
    train(args.epochs, args.batch, args.lr, n_samples=n, checkpoint=args.checkpoint)
