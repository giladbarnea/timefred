import os
import re
import sys
from pathlib import Path
from typing import Optional, Any

import toml
# from pydantic import BaseModel, Field
from timefred.field import Field
from timefred.space import Space, DictSpace


class Config(DictSpace):
    class TimeCfg(DictSpace):
        class TimeFormats(DictSpace):
            date: str = 'DD/MM/YY'
            short_date: str = 'DD/MM'
            time: str = 'HH:mm:ss'
            short_time: str = 'HH:mm'
            datetime: str = f'{date} {time}'
            short_datetime: str = f'{short_date} {short_time}'

            def __init__(self, mappable=(), **kwargs) -> None:
                super().__init__(mappable, **kwargs)
                self.date_separator = re.search(r'[^\w]', self.date).group()
                self.time_separator = re.search(r'[^\w]', self.time).group()

        # tz: BaseTzInfo
        # tz: datetime.timezone = dt.now().astimezone().tzinfo
        # tz: datetime.tzinfo = dt.now().astimezone().tzinfo
        tz = 'Asia/Jerusalem'
        formats: TimeFormats = Field(default_factory=TimeFormats, cast=TimeFormats)

        # def __init__(self, timecfg: dict):
        #     super().__init__(timecfg)
        # self.tz = timezone(self.tz)

    class DevCfg(DictSpace):
        debugger: Optional[str] = Field(default_factory=str)
        traceback: Optional[str]= Field(default_factory=str)
        # features: Optional[BaseModel]

    class Sheet(DictSpace):
        path = os.path.expanduser(os.environ.get('TF_SHEET', "~/timefred-sheet.toml"))
    
    time: TimeCfg = Field(default_factory=TimeCfg, cast=TimeCfg)
    sheet: Sheet = Field(default_factory=Sheet, cast=Sheet)
    dev: Optional[DevCfg] = Field(default_factory=DevCfg, cast=DevCfg)
    
    def __init__(self):
        cfg_file = Path(os.path.expanduser(os.environ.get('TF_CONFIG_PATH', "~/.timefred.toml")))
        
        if cfg_file.exists():
            cfg = toml.load(cfg_file.open())
        else:
            self._create_default_config_file(cfg_file)
            cfg = {}
        super().__init__(**cfg)
        if self.dev.debugger:
            os.environ['PYTHONBREAKPOINT'] = self.dev.debugger
        if self.dev.traceback:
            try:
                if self.dev.traceback == "rich.traceback":
                    from rich.traceback import install
                    install(show_locals=True)
                else:
                    print(f"Don't support {self.dev.traceback}", file=sys.stderr)
            except Exception as e:
                print(f'{e.__class__.__qualname__} caught in {self}.__init__: {e}', file=sys.stderr)
    
    def _create_default_config_file(self, cfg_file: Path):
        raise NotImplementedError
        constructed = self.dict()
        toml.dump(constructed, cfg_file.open(mode="x"))

config = Config()
