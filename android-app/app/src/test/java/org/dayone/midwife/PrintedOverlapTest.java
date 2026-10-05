package org.dayone.midwife;
import org.junit.Test;
import static org.junit.Assert.*;

public class PrintedOverlapTest {
    @Test public void rotatedLabelsAndBothWindings() {
        float[][] q={{10,0},{20,10},{10,20},{0,10}};
        assertTrue(PrintedOverlap.contains(q,10,10));assertFalse(PrintedOverlap.contains(q,1,1));
        assertTrue(PrintedOverlap.contains(new float[][]{q[3],q[2],q[1],q[0]},10,10));
    }
    @Test public void bordersAreIncludedButDegenerateAndNonfiniteAreRejected() {
        assertTrue(PrintedOverlap.contains(new float[][]{{0,0},{10,0},{10,10},{0,10}},0,5));
        assertFalse(PrintedOverlap.contains(new float[][]{{0,0},{1,1},{2,2},{3,3}},1,1));
        assertFalse(PrintedOverlap.contains(new float[][]{{0,0},{10,0},{10,10},{0,10}},Double.NaN,5));
    }
}
