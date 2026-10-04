package org.dayone.midwife;
import android.content.Context;
import org.json.*;
import java.io.*;
import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** Authenticated localhost only; adb reverse carries requests over USB. */
public final class UsbDatabaseSink implements RecordSink {
    private final Context context;
    public UsbDatabaseSink(Context c){context=c.getApplicationContext();}
    private JSONObject request(String path,JSONObject body)throws Exception {
        File auth=new File(context.getFilesDir(),"usb-sync-token");
        if(!auth.isFile())throw new IOException("Connect and pair USB sync on the PC.");
        String token=new String(Files.readAllBytes(auth.toPath()),StandardCharsets.UTF_8).trim();
        // Unix-domain socket, not an IP socket: works without INTERNET permission.
        try(LocalSocket socket=new LocalSocket()){
            socket.connect(new LocalSocketAddress("sanad-usb-db",LocalSocketAddress.Namespace.ABSTRACT));
            socket.setSoTimeout(body==null?1500:10000);
            byte[] data=body==null?new byte[0]:body.toString().getBytes(StandardCharsets.UTF_8);
            String header=(body==null?"GET ":"POST ")+path+" HTTP/1.0\r\nHost: localhost\r\nAuthorization: Bearer "+token+"\r\nContent-Type: application/json\r\nContent-Length: "+data.length+"\r\nConnection: close\r\n\r\n";
            OutputStream out=socket.getOutputStream();out.write(header.getBytes(StandardCharsets.US_ASCII));out.write(data);out.flush();
            InputStream in=socket.getInputStream();ByteArrayOutputStream response=new ByteArrayOutputStream();byte[] buffer=new byte[2048];int n;
            while((n=in.read(buffer))!=-1){if(response.size()+n>65536)throw new IOException("Invalid PC response");response.write(buffer,0,n);}
            String reply=response.toString("UTF-8");int split=reply.indexOf("\r\n\r\n");
            if(split<0||!reply.startsWith("HTTP/1.0 200 ")&&!reply.startsWith("HTTP/1.1 200 "))throw new IOException("PC database did not acknowledge upload.");
            return new JSONObject(reply.substring(split+4));
        }
    }
    public boolean checkConnection()throws Exception{return request("/health",null).optString("service").equals("sanad-usb-db-v1");}
    public boolean reachable(){try{return checkConnection();}catch(Exception e){return false;}}
    @Override public void upload(JSONObject record)throws Exception {
        JSONObject payload=new JSONObject(record.toString());payload.remove("pc_receipt");payload.remove("synced_at");payload.remove("sync_error");payload.put("state","REGISTERED");
        JSONArray history=payload.optJSONArray("lifecycle"),kept=new JSONArray();if(history!=null)for(int i=0;i<history.length();i++){JSONObject item=history.getJSONObject(i);String state=item.optString("state");if(!state.equals("SYNCED")&&!state.equals("SYNC_FAILED"))kept.put(item);}payload.put("lifecycle",kept);
        JSONObject ack=request("/records",payload);
        if(!ack.optString("id").equals(record.getString("id"))||!ack.optBoolean("committed"))throw new IOException("PC did not confirm database commit.");
        record.put("pc_receipt",ack);
    }
}
