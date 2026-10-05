package org.dayone.midwife;

/** Separable, antialiased RGB bilinear resize matching Pillow's 8-bit path.
 * Android Canvas filtering samples only neighboring pixels when reducing an image;
 * training uses a triangular filter widened to cover the source footprint.
 */
final class BilinearResampler {
    private static final int PRECISION = 22;
    private static final int ROUND = 1 << (PRECISION - 1);

    private static final class Kernel {
        final int[] start;
        final int[][] weights;
        Kernel(int source, int target) {
            start = new int[target]; weights = new int[target][];
            double scale = (double) source / target, support = Math.max(1, scale);
            for (int x = 0; x < target; x++) {
                double center = (x + .5) * scale;
                int first = Math.max(0, (int) (center - support + .5));
                int end = Math.min(source, (int) (center + support + .5));
                start[x] = first;
                double[] values = new double[end - first];
                double sum = 0;
                for (int j = 0; j < values.length; j++) {
                    values[j] = Math.max(0, 1 - Math.abs((first + j - center + .5) / support));
                    sum += values[j];
                }
                weights[x] = new int[values.length];
                for (int j = 0; j < values.length; j++)
                    weights[x][j] = (int) (values[j] / sum * (1 << PRECISION) + .5);
            }
        }
    }

    static int[] resize(int[] source, int sw, int sh, int dw, int dh) {
        if (sw <= 0 || sh <= 0 || dw <= 0 || dh <= 0 || source.length != sw * sh)
            throw new IllegalArgumentException("Invalid image dimensions");
        int[] horizontal = source;
        if (sw != dw) {
            Kernel kernel = new Kernel(sw, dw);
            horizontal = new int[dw * sh];
            for (int y = 0; y < sh; y++) for (int x = 0; x < dw; x++)
                horizontal[y * dw + x] = filter(source, y * sw + kernel.start[x], 1, kernel.weights[x]);
        }
        if (sh == dh) return horizontal;
        Kernel kernel = new Kernel(sh, dh);
        int[] output = new int[dw * dh];
        for (int y = 0; y < dh; y++) for (int x = 0; x < dw; x++)
            output[y * dw + x] = filter(horizontal, kernel.start[y] * dw + x, dw, kernel.weights[y]);
        return output;
    }

    private static int filter(int[] pixels, int offset, int stride, int[] weights) {
        int r = ROUND, g = ROUND, b = ROUND;
        for (int j = 0; j < weights.length; j++) {
            int pixel = pixels[offset + j * stride], weight = weights[j];
            r += (pixel >> 16 & 255) * weight;
            g += (pixel >> 8 & 255) * weight;
            b += (pixel & 255) * weight;
        }
        return 0xff000000 | Math.min(255, r >> PRECISION) << 16
                | Math.min(255, g >> PRECISION) << 8 | Math.min(255, b >> PRECISION);
    }
}
