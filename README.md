# Awesome Picbooks

用于存放绘本图片和整理后的绘本故事文本。

## 目录结构

```text
images/                         # 绘本图片，按绘本名称分文件夹存放
stories/plain/                  # 原始绘本故事文字
stories/with-page-turns/        # 加入翻页提示语后的绘本故事文字
```

## 使用方式

1. 在 `images/` 下为每本绘本创建一个文件夹，例如：

   ```text
   images/飞天大面包/
   ```

2. 把该绘本的图片放入对应文件夹。

3. 图片建议按页序命名，或使用连续拍摄生成的文件名，例如：

   ```text
   001.jpg
   002.jpg
   003.jpg
   ```

4. 处理完成后，会生成两份文本：

   - `stories/plain/<story-name>.txt`：原始绘本故事文字
   - `stories/with-page-turns/<story-name>.txt`：加入“请翻到下一页。”等提示语的版本

## 已整理绘本

- 飞天大面包

## 翻页提示

默认翻页提示语：

```text
请翻到下一页。
```

提示语只插入在两页之间，最后一页后不会再添加。
