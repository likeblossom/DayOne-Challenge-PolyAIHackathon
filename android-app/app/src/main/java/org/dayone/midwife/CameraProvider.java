package org.dayone.midwife;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.*;

/** A single private temporary capture file, shared only through URI grants. */
public final class CameraProvider extends ContentProvider {
    public static final Uri URI=Uri.parse("content://org.dayone.midwife.camera/capture.jpg");
    @Override public boolean onCreate() { return true; }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        if(!URI.equals(uri)) throw new FileNotFoundException("Unknown capture");
        return ParcelFileDescriptor.open(new File(getContext().getCacheDir(),"capture.jpg"),ParcelFileDescriptor.parseMode(mode));
    }
    @Override public String getType(Uri uri) { return "image/jpeg"; }
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort) { return null; }
    @Override public Uri insert(Uri uri,ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri,String selection,String[] args) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri,ContentValues values,String selection,String[] args) { throw new UnsupportedOperationException(); }
}
