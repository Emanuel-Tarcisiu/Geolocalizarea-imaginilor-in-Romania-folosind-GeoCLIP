import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from geoclip import GeoCLIP
from geoclip.train.dataloader import GeoDataLoader, img_train_transform, img_val_transform
from geoclip.train import train
from datetime import datetime
from geoclip.train.eval import eval_images

os.environ['CUDA_VISIBLE_DEVICES'] = '4,5' # '4,5,6,7'
NUM_GPUS = torch.cuda.device_count()

MODEL_ITERATION = sys.argv[1] if len(sys.argv) > 1 else '0'
BATCH_SIZE = 128
NUM_EPOCHS = 50
LEARNING_RATE = 8e-5
WEIGHT_DECAY = 1e-5
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CSV_PATH_TRAIN = '/home/eorsan/creare_dataset/antrenare/landmarks_antrenare_mare.csv'
CSV_PATH_VAL = '/home/eorsan/creare_dataset/antrenare/val_dataset.csv'
IMAGES_DIR = '/home/eorsan/creare_dataset/antrenare/imagini'
SAVE_MODEL_PATH = '/home/eorsan/antrenare_model/model'
SAVE_MODEL_ITERATION_PATH = f'/home/eorsan/antrenare_model/model/iterations_{MODEL_ITERATION}'
LOG_PATH = '/home/eorsan/antrenare_model/log.train'
SAVE_ACCURACIES_PATH = '/home/eorsan/antrenare_model/accuracies'
SAVE_LOSSES_PATH = '/home/eorsan/antrenare_model/losses'

LOG_ENTRY_MSG = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '\n'
LOG_DONE_MSG = 'Training done!\n\n'
LOG_DEVICE_MSG = f"Device: {DEVICE}"
LOG_NUM_GPUS_MSG = f"Number of GPUs: {NUM_GPUS}\n"


def write_log(log_msg: str) -> None:
    with open(LOG_PATH, 'a') as f:
        f.write(log_msg + '\n')

def verifica_fisiere() -> bool:
    return os.path.exists(CSV_PATH_TRAIN) and os.path.exists(CSV_PATH_VAL) \
        and os.path.exists(IMAGES_DIR) and os.path.isdir(IMAGES_DIR)

def save_accuracies(accuracies: list, dist: int) -> None:
    filename = os.path.join(SAVE_ACCURACIES_PATH, f'accuracies_{dist}_{MODEL_ITERATION}.txt')
    with open(filename, 'w') as f:
        for acc in accuracies:
            f.write(f"{acc}\n")

def save_losses(losses: list) -> None:
    filename = os.path.join(SAVE_LOSSES_PATH, f'losses_{MODEL_ITERATION}.txt')
    with open(filename, 'w') as f:
        for loss in losses:
            f.write(f"{loss}\n")

def main_finetune() -> None:
    if not verifica_fisiere():
        write_log("Fisiere non existante\n")
        exit(1)
    
    os.makedirs(SAVE_MODEL_PATH, exist_ok=True)
    os.makedirs(SAVE_MODEL_ITERATION_PATH, exist_ok=True)
    os.makedirs(SAVE_ACCURACIES_PATH, exist_ok=True)
    os.makedirs(SAVE_LOSSES_PATH, exist_ok=True)

    train_dataset = GeoDataLoader(
        dataset_file=CSV_PATH_TRAIN,
        dataset_folder=IMAGES_DIR,
        transform=img_train_transform()
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=4,
        drop_last=True,
        pin_memory=True if DEVICE == 'cuda' else False
    )

    val_dataset = GeoDataLoader(
        dataset_file=CSV_PATH_VAL,
        dataset_folder=IMAGES_DIR,
        transform=img_val_transform()
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=4,
        drop_last=False,
        pin_memory=True if DEVICE == 'cuda' else False
    )

    write_log(LOG_DEVICE_MSG)

    model = GeoCLIP()
    model.to(DEVICE)

    write_log(LOG_NUM_GPUS_MSG)
    if NUM_GPUS > 1: 
        model = nn.DataParallel(model)

    optimizer = optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        betas=(0.9, 0.999),
        eps=1e-8
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
    criterion = nn.CrossEntropyLoss()

    best_loss = float('inf')
    best_acc_25km = 0.0
    best_acc_1km = 0.0
    patience_loss = 8
    patience_counter_loss = 0
    losses = []
    accuracies_25km = []
    accuracies_1km = []
    
    for epoch in range(NUM_EPOCHS):
        epoch_loss = train(
            train_dataloader=train_loader,
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            batch_size=BATCH_SIZE,
            device=DEVICE,
            scheduler=scheduler,
            criterion=criterion
        )

        losses.append(epoch_loss)

        current_lr = scheduler.get_last_lr()[0]
        write_log(f"Epoch {epoch+1}/{NUM_EPOCHS} - Train Loss: {epoch_loss:.6f}, LR: {current_lr:.8f}")

        # evaluare pe setul de validare
        eval_results = eval_images(
            val_dataloader=val_loader,
            model=model,
            device=DEVICE
        )

        current_acc_25km = eval_results.get('acc_25_km', 0.0)
        current_acc_1km = eval_results.get('acc_1_km', 0.0)
        accuracies_25km.append(current_acc_25km)
        accuracies_1km.append(current_acc_1km)
        
        # verificare acuratete
        if current_acc_25km > best_acc_25km:
            best_acc_25km = current_acc_25km
            write_log(f"Noul best accuracy (25km): {best_acc_25km:.4f}")

            if isinstance(model, nn.DataParallel):
                model.module.save_weights(
                    save_dir=SAVE_MODEL_PATH,
                    iteration_id=f'{MODEL_ITERATION}_bestacc_25km'
                )
            else:
                model.save_weights(
                    save_dir=SAVE_MODEL_PATH,
                    iteration_id=f'{MODEL_ITERATION}_bestacc_25km'
                )

        if current_acc_1km > best_acc_1km:
            best_acc_1km = current_acc_1km
            write_log(f"Noul best accuracy (1km): {best_acc_1km:.4f}")

            if isinstance(model, nn.DataParallel):
                model.module.save_weights(
                    save_dir=SAVE_MODEL_PATH,
                    iteration_id=f'{MODEL_ITERATION}_bestacc_1km'
                )
            else:
                model.save_weights(
                    save_dir=SAVE_MODEL_PATH,
                    iteration_id=f'{MODEL_ITERATION}_bestacc_1km'
                )

        # salvare intermediara
        if (epoch + 1) % 5 == 0:
            if isinstance(model, nn.DataParallel):
                model.module.save_weights(
                    save_dir=SAVE_MODEL_ITERATION_PATH,
                    iteration_id=epoch + 1
                )
            else:
                model.save_weights(
                    save_dir=SAVE_MODEL_ITERATION_PATH,
                    iteration_id=epoch + 1
                )
            write_log(f'Iteratie intermediara salvata cu id-ul {epoch + 1}, in {SAVE_MODEL_ITERATION_PATH}')

        # verificare early stopping loss
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            patience_counter_loss = 0
            if isinstance(model, nn.DataParallel):
                model.module.save_weights(
                    save_dir=SAVE_MODEL_PATH,
                    iteration_id=f'{MODEL_ITERATION}_bestloss'
                )
            else:
                model.save_weights(
                    save_dir=SAVE_MODEL_PATH,
                    iteration_id=f'{MODEL_ITERATION}_bestloss'
                )
            write_log(f"Noul best loss = {best_loss}")
        else: patience_counter_loss += 1

        if patience_counter_loss >= patience_loss:
            write_log(f'Early stopping la epoca {epoch + 1} (patience_loss: {patience_loss})')
            break

        if epoch > 5 and epoch_loss > losses[0] * 2: write_log(f'Epoca: {epoch + 1} - posibila divergenta => trebuie sa reduci LR')

    # salveaza modelul final
    if isinstance(model, nn.DataParallel):
        model.module.save_weights(
            save_dir=SAVE_MODEL_PATH,
            iteration_id=MODEL_ITERATION
        )
    else:
        model.save_weights(
            save_dir=SAVE_MODEL_PATH,
            iteration_id=MODEL_ITERATION
        )

    save_accuracies(accuracies_25km, 25)
    save_accuracies(accuracies_1km, 1)
    save_losses(losses)

    write_log(f'Iteratie salvata cu id-ul: {MODEL_ITERATION}')


if __name__ == "__main__":
    write_log(LOG_ENTRY_MSG)
    main_finetune()
    write_log(LOG_DONE_MSG)
