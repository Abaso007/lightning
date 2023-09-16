from lightning import LightningApp, LightningFlow


class Flow(LightningFlow):
    def __init__(self):
        super().__init__()
        self.names = []

    def run(self):
        print(self.names)

    def add_name(self, name: str):
        """Add a name."""
        print(f"Received name: {name}")
        self.names.append(name)

    def configure_commands(self):
        return [
            {"add": self.add_name},
        ]


app = LightningApp(Flow())
