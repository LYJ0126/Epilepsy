import torch
from net import EnhancedEpilepsyDetector

def pth2onnx(model_path):
    # 初始化设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # 加载模型
    model = EnhancedEpilepsyDetector().to(device)
    model.load_state_dict(torch.load(model_path))
    model.eval()

    # 创建虚拟输入
    dummy_input = torch.randn(1, 18, 21, 60).to(device)
    
    # 导出模型到 ONNX
    torch.onnx.export(
        model,
        dummy_input,
        "model.onnx",
        opset_version=11,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "output": {0: "batch_size"}
        }
    )
    print("模型已导出为 model.onnx")

if __name__ == '__main__':
    model_path = 'saved_models/epilepsy_cnn_best_model.pth'
    pth2onnx(model_path)