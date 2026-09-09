"""Deterministic SBGC-221 profile test-user seeder."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from games.models import Game

from users.models import UserProfile, UserTopGame

STEAM_URL_THENAMESAMMARIS = "https://steamcommunity.com/id/thenamesammaris"

THENAMESAMMARIS_TOP_GAMES = [
    "Hades",
    "Elden Ring",
    "Wobbly Life",
    "Dota 2",
    "Wuthering Waves",
    "Persona 4 Golden",
]


class Command(BaseCommand):
    help = "Seed the two deterministic SBGC-221 test profiles."

    def handle(self, *args, **options):
        self._seed_thenamesammaris()
        self._seed_james()
        self.stdout.write(self.style.SUCCESS("Profile test users seeded."))

    def _seed_thenamesammaris(self) -> None:
        user, _ = User.objects.get_or_create(
            username="thenamesammaris",
            defaults={"first_name": "", "last_name": ""},
        )
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "bio": (
                    "Roguelites, tactical shooters, and cozy sandboxes are my "
                    "rotation. I chase perfect runs in Hades, coordinate stacks "
                    "in Dota 2, and lose weekends to open worlds. If a game "
                    "rewards curiosity, precision, or patience, I am already "
                    "two hundred hours deep."
                ),
                "avatar_key": "anime_male_4",
                "border_type": UserProfile.BorderType.PRESET,
                "border_preset_id": 1,
                "steam_profile_url": STEAM_URL_THENAMESAMMARIS,
            },
        )
        self._set_top_games(profile, THENAMESAMMARIS_TOP_GAMES)

    def _seed_james(self) -> None:
        user, _ = User.objects.get_or_create(
            username="james",
            defaults={"first_name": "James", "last_name": "Bond"},
        )
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "bio": (
                    "我是一名热爱电子游戏的玩家，从中学时代起就沉迷于各种类型的游戏世界。"
                    "我喜欢挑战高难度的动作游戏，也享受在开放世界角色扮演游戏中探索每一个角落。"
                    "策略游戏让我学会思考和规划，休闲游戏则帮助我在忙碌的生活中找到片刻的宁静。"
                    "最近我迷上了魂系游戏，那种在失败中不断成长的体验让我着迷。"
                    "游戏对我来说不仅仅是一种娱乐方式，更是一种艺术表达。"
                    "如果你也喜欢游戏，欢迎来找我交流心得。"
                    "我喜欢在游戏中寻找隐藏的细节和秘密，这让我很有成就感。"
                    "每个周末我都会和朋友一起联机玩游戏，分享彼此的快乐。"
                    "我认真对待每一款优秀游戏作品。"
                ),
                "avatar_key": "male_1",
                "border_type": UserProfile.BorderType.SOLID,
                "border_color": "#00FFCC",
                "steam_profile_url": "",
            },
        )

    def _set_top_games(self, profile: UserProfile, names: list[str]) -> None:
        UserTopGame.objects.filter(profile=profile).delete()
        rank = 1
        for name in names:
            game = Game.objects.filter(name__iexact=name).first()
            if game is None:
                self.stdout.write(
                    self.style.WARNING(f"Game not found, skipping: {name}")
                )
                continue
            UserTopGame.objects.create(profile=profile, game=game, rank=rank)
            rank += 1
