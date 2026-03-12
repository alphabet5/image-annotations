import logging
from pathlib import Path

import click


def _common_options(f):
    f = click.option(
        "--annotations",
        "annotations_path",
        default="annotations.tsv",
        type=click.Path(),
        show_default=True,
        help="TSV file for annotations.",
    )(f)
    f = click.option(
        "--images",
        "images_dir",
        default=".",
        type=click.Path(exists=True, file_okay=False),
        show_default=True,
        help="Folder to load in file tree (defaults to cwd).",
    )(f)
    f = click.option(
        "-v", "--verbose",
        is_flag=True,
        default=False,
        help="Enable DEBUG logging to stderr.",
    )(f)
    return f


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Image annotation tool.  Defaults to 'ui' when no command is given."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(launch_ui)


@cli.command("ui")
@_common_options
def launch_ui(annotations_path, images_dir, verbose):
    """Launch the graphical annotation interface."""
    _setup_logging(verbose)
    from .app import launch_gui
    launch_gui(
        images_dir=Path(images_dir),
        annotations_file=Path(annotations_path),
    )


@cli.command("generate-images")
@_common_options
@click.option(
    "--format",
    "filename_template",
    default="{{image_file_no_ext}}-annotated.png",
    show_default=True,
    help=(
        "Jinja2 template for output filename. "
        "Variables: image_file, image_file_no_ext, imageX, imageY"
    ),
)
def generate_images(annotations_path, images_dir, verbose, filename_template):
    """Render annotations onto copies of images and save to disk."""
    _setup_logging(verbose)

    from collections import defaultdict

    from jinja2 import Template
    from PIL import Image

    from .renderer import render_annotations_onto_image
    from .tsv_io import load_annotations

    log = logging.getLogger(__name__)

    tsv_path = Path(annotations_path)
    log.debug("Loading annotations from %s", tsv_path.resolve())
    annotations, session_config = load_annotations(tsv_path)
    log.debug("Loaded %d annotation(s)", len(annotations))

    if not annotations:
        click.echo("No annotations found.")
        return

    annotation_styles = session_config.get("annotation_styles", {})
    show_labels = session_config.get("show_labels", True)
    show_coordinates = session_config.get("show_coordinates", False)

    by_image: dict[str, list] = defaultdict(list)
    for ann in annotations:
        by_image[ann["image_file"]].append(ann)

    images_root = Path(images_dir)
    template = Template(filename_template)
    errors = 0

    for image_file, anns in by_image.items():
        img_path = images_root / image_file
        log.debug("Processing %s (%d annotation(s))", img_path, len(anns))
        if not img_path.exists():
            click.echo(f"WARNING: image not found: {img_path}", err=True)
            errors += 1
            continue

        try:
            with Image.open(img_path) as img:
                iw, ih = img.size

            out_name = template.render(
                image_file=image_file,
                image_file_no_ext=Path(image_file).stem,
                imageX=iw,
                imageY=ih,
            )
            out_path = img_path.parent / out_name
            actual_out_path = (
                out_path.with_suffix(".png")
                if out_path.suffix.lower() in {".heic", ".heif"}
                else out_path
            )
            render_annotations_onto_image(
                img_path, anns, out_path,
                annotation_styles=annotation_styles,
                show_labels=show_labels,
                show_coordinates=show_coordinates,
            )
            click.echo(f"Saved: {actual_out_path}")
        except Exception as e:
            click.echo(f"ERROR processing {img_path}: {e}", err=True)
            errors += 1

    if errors:
        click.echo(f"\n{errors} file(s) had errors.", err=True)
