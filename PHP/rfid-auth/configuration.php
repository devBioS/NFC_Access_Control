<?php
$json_rfid_userdb = "rfid.txt";
$json_gauth_userdb = "googleauth.txt";
$unknown_uid_log = "unknown_uids.txt";

$hmac_hash_key = 'YourSecretKeyForTagKeyGeneration'; //be sure this is unique

$ctx = stream_context_create(
    array(
        'http' => array(
            'timeout' => 1,
            'header'=>"Connection: close"
        ),
        'https' => array (
            'timeout' => 1,
            'header'=>"Connection: close"
        )
    )
);

//open door command(s)
function door_open($device_id,$uid) {
    global $ctx;
    //file_get_contents("http://localhost/fhem?cmd.Doorlock=set%20Doorlock%20open&XHR=1",0,$ctx); //I use FHEM
}
//close door command(s)
function door_close($device_id,$uid) {
    global $ctx;
    //file_get_contents("http://localhost/fhem?cmd.Doorlock=set%20Doorlock%20lock&XHR=1",0,$ctx);
}

//toogle door command(s) used for GAuth only
function door_toggle($device_id,$uid) {
    global $ctx;
    /*$state=file_get_contents("http://localhost/fhem?cmd={ReadingsVal(%22Doorlock%22%2C%22state%22%2C%22%22)}&XHR=1",0,$ctx);
    if (trim($state) == "unlocked") {
            file_get_contents("http://localhost/fhem?cmd.Doorlock=set%20Doorlock%20lock&XHR=1",0,$ctx);
    } else {
            file_get_contents("http://localhost/fhem?cmd.Doorlock=set%20Doorlock%20open&XHR=1",0,$ctx);
    }*/
}

//China UID changeable tag detected. What to do?
function china_uid_detected($device_id,$uid,$name) {
    global $ctx;
    //file_get_contents("http://localhost/fhem?cmd.telegram=set%20telegram%20message%20@12345678%20!!!%20Cloned%20UID%20".$uid."%20%20for%20fob%20".$name."%20detected%20at%20door%20access%20!!!&XHR=1",0,$ctx);
}

//Unknown UID detected. What to do?
function unknown_uid_detected($device_id,$uid) {
    global $ctx;
    //file_get_contents("http://localhost/fhem?cmd.telegram=set%20telegram%20message%20@12345678%20!!!%20Unknown%20RFID%20UID%20detected:".$uid."!!!&XHR=1",0,$ctx);
}


?>