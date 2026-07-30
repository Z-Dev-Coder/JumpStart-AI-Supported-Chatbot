from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps, UnidentifiedImageError

from store.management.commands.seed_data import PRODUCTS, product_image_path


class Command(BaseCommand):
    help = "Download demo product images into MEDIA_ROOT/products."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-download images that already exist.")
        parser.add_argument("--timeout", type=int, default=30, help="Download timeout in seconds.")

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        products_dir = media_root / "products"
        products_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        skipped = 0
        failed = 0

        for product in PRODUCTS:
            slug = product["slug"]
            source_url = product.get("image_url")
            target = media_root / product_image_path(slug)

            if target.exists() and not options["force"]:
                skipped += 1
                self.stdout.write(f"  Skipped existing: {target.relative_to(media_root)}")
                continue

            if not source_url:
                failed += 1
                self.stderr.write(f"  Missing source URL for: {slug}")
                continue

            try:
                data = self._download(source_url, options["timeout"])
                self._save_jpeg(data, target)
            except (HTTPError, URLError, TimeoutError, UnidentifiedImageError, OSError) as exc:
                failed += 1
                self.stderr.write(f"  Failed {slug}: {exc}")
                continue

            downloaded += 1
            self.stdout.write(f"  Downloaded: {target.relative_to(media_root)}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Product images ready. Downloaded: {downloaded}, skipped: {skipped}, failed: {failed}"
            )
        )

    def _download(self, source_url, timeout):
        request = Request(
            source_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    def _save_jpeg(self, data, target):
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                alpha = image.getchannel("A")
                background.paste(image, mask=alpha)
                image = background
            else:
                image = image.convert("RGB")

            image.thumbnail((900, 900), Image.Resampling.LANCZOS)
            image.save(target, "JPEG", quality=88, optimize=True)
