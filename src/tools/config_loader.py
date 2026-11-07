import yaml
import os

def load_employee_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir,"employee.yaml")

    try:
        with open(config_path,"r",encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        print(f"读取配置失败：{e}")
        return None