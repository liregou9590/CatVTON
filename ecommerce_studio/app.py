import base64
import os
import tempfile
import zipfile
from contextlib import ExitStack
from pathlib import Path

import gradio as gr
from openai import OpenAI

DEFAULT_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
DEFAULT_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "high")
DEFAULT_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")


def _path(value):
    if value is None:
        return None
    return getattr(value, "name", value)


def _build_prompt(mode: str) -> str:
    common = (
        "Create a photorealistic ecommerce product image. "
        "Keep the base image camera angle, crop, pose, body proportions, hands, lighting, "
        "background, shadows and overall composition unchanged unless a tiny adjustment is "
        "required for natural realism. Avoid adding text, logos, jewelry or accessories that "
        "are not present in the references."
    )

    if mode == "一键换衣":
        return (
            "Image 1 is the base model photo. Image 2 is the garment/pajama reference. "
            "Edit Image 1 so the model wears the garment from Image 2. Faithfully preserve "
            "the garment's exact color, print, fabric appearance, piping, buttons, collar, "
            "sleeve length, trouser length, seams and silhouette. Do not change the model's "
            "face, identity, hairstyle or skin tone. " + common
        )

    if mode == "一键换脸":
        return (
            "Image 1 is the base model photo. Image 2 is the authorized face reference. "
            "Replace only the facial identity in Image 1 so it matches Image 2 naturally. "
            "Preserve the base image hairstyle, clothing, body, pose, background, lighting "
            "and crop. Keep the face photorealistic and anatomically consistent. " + common
        )

    return (
        "Image 1 is the base model photo. Image 2 is the garment/pajama reference. "
        "Image 3 is the authorized face reference. Edit Image 1 so the model wears the "
        "garment from Image 2 and the facial identity matches Image 3. Faithfully preserve "
        "the garment's exact color, print, fabric appearance, piping, buttons, collar, "
        "sleeve length, trouser length, seams and silhouette. Preserve the base image pose, "
        "body proportions, hairstyle, background, camera angle, crop and lighting. "
        "Make both edits look like one natural studio photograph. " + common
    )


def _edit_one(client, image_paths, prompt, model, quality, size, output_path):
    with ExitStack() as stack:
        files = [stack.enter_context(open(p, "rb")) for p in image_paths]
        result = client.images.edit(
            model=model,
            image=files,
            prompt=prompt,
            quality=quality,
            size=size,
        )

    if not result.data or not result.data[0].b64_json:
        raise RuntimeError("OpenAI image edit returned no image data")

    output_path.write_bytes(base64.b64decode(result.data[0].b64_json))


def process_batch(
    person_files,
    cloth_file,
    face_file,
    mode,
    model,
    quality,
    size,
    authorized,
):
    if not authorized:
        raise gr.Error("请先确认你拥有这些人物肖像和服装素材的使用授权。")

    if not person_files:
        raise gr.Error("请至少上传 1 张模特原图。")

    person_paths = [_path(x) for x in person_files]
    cloth_path = _path(cloth_file)
    face_path = _path(face_file)

    if mode in ("一键换衣", "换衣 + 换脸") and not cloth_path:
        raise gr.Error("当前模式需要上传睡衣/服装参考图。")
    if mode in ("一键换脸", "换衣 + 换脸") and not face_path:
        raise gr.Error("当前模式需要上传脸部参考图。")

    client = OpenAI()
    prompt = _build_prompt(mode)

    workdir = Path(tempfile.mkdtemp(prefix="ecommerce_studio_"))
    output_dir = workdir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    failures = []

    for index, person_path in enumerate(person_paths, start=1):
        try:
            refs = [person_path]
            if mode in ("一键换衣", "换衣 + 换脸"):
                refs.append(cloth_path)
            if mode in ("一键换脸", "换衣 + 换脸"):
                refs.append(face_path)

            stem = Path(person_path).stem
            out_path = output_dir / f"{index:03d}_{stem}_edited.png"
            _edit_one(
                client=client,
                image_paths=refs,
                prompt=prompt,
                model=model,
                quality=quality,
                size=size,
                output_path=out_path,
            )
            outputs.append(str(out_path))
        except Exception as exc:
            failures.append(f"{Path(person_path).name}: {exc}")

    if not outputs:
        raise gr.Error("本批次全部生成失败，请检查 API Key、额度、图片格式或模型权限。")

    zip_path = workdir / "ecommerce_results.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in outputs:
            zf.write(file_path, arcname=Path(file_path).name)
        if failures:
            zf.writestr("failures.txt", "\n".join(failures))

    status = (
        f"完成：{len(outputs)} 张；失败：{len(failures)} 张。"
        + (" 失败明细已写入 ZIP 内 failures.txt。" if failures else "")
    )
    return status, str(zip_path), outputs


with gr.Blocks(title="电商睡衣批量换衣 / 换脸") as demo:
    gr.Markdown(
        """
# 电商睡衣批量一键换衣 / 一键换脸
批量上传模特图，选择睡衣参考图和脸部参考图，一键生成电商成片并打包 ZIP。

> 建议先用 3–5 张图测试提示词和质量，再放大批量。
"""
    )

    with gr.Row():
        with gr.Column(scale=2):
            person_files = gr.Files(
                label="1. 模特原图（可多选）",
                file_types=["image"],
                type="filepath",
            )
            cloth_file = gr.File(
                label="2. 睡衣 / 服装参考图",
                file_types=["image"],
                type="filepath",
            )
            face_file = gr.File(
                label="3. 模特脸部参考图",
                file_types=["image"],
                type="filepath",
            )

        with gr.Column(scale=1):
            mode = gr.Radio(
                ["一键换衣", "一键换脸", "换衣 + 换脸"],
                value="换衣 + 换脸",
                label="处理模式",
            )
            model = gr.Dropdown(
                ["gpt-image-2.5-sunburst", "gpt-image-2.5-flare"],
                value=DEFAULT_MODEL,
                allow_custom_value=True,
                label="图像模型",
            )
            quality = gr.Dropdown(
                ["medium", "high", "xhigh", "max"],
                value=DEFAULT_QUALITY,
                label="质量",
            )
            size = gr.Dropdown(
                ["1024x1536", "1536x1024", "1024x1024"],
                value=DEFAULT_SIZE,
                allow_custom_value=True,
                label="输出尺寸",
            )
            authorized = gr.Checkbox(
                label="我确认对人物肖像和服装素材拥有使用授权",
                value=False,
            )
            run_btn = gr.Button("开始批量生成", variant="primary")

    status = gr.Markdown()
    zip_file = gr.File(label="批量结果 ZIP")
    gallery = gr.Gallery(label="生成预览", columns=4, height="auto")

    run_btn.click(
        fn=process_batch,
        inputs=[
            person_files,
            cloth_file,
            face_file,
            mode,
            model,
            quality,
            size,
            authorized,
        ],
        outputs=[status, zip_file, gallery],
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2).launch(server_name="0.0.0.0")
