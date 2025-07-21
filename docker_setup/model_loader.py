from _geoclip import GeoCLIP
import tempfile
from PIL import Image
import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_model(model_path: str) -> GeoCLIP:
    model = GeoCLIP(from_pretrained=False)
    model.load_finetuned_weights(
        weight_dir=model_path,
        iteration_id='24_bestacc_1km'
    )
    model.to(DEVICE)
    model.eval()

    return model

def predict_image(model, file_storage, k=5):
    image = Image.open(file_storage).convert("RGB")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as temp_file:
        image.save(temp_file.name)
        predictions = model.predict(image_path=temp_file.name, top_k=k)

    def convert_to_serializable(obj):
        if isinstance(obj, tuple):
            return [convert_to_serializable(item) for item in obj]
        elif isinstance(obj, list):
            return [convert_to_serializable(item) for item in obj]
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        elif hasattr(obj, 'numpy'):
            return obj.numpy().tolist()
        else:
            return obj

    return convert_to_serializable(predictions)