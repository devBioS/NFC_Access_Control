<?php
/*
#---------------------------------------------------
# NFC Door Access Control
#---------------------------------------------------
# Copyright (c) 2020 devBioS 
# With enough persistence everything is possible
# https://github.com/devBioS/NFC_Access_Control
#
# Licensed under the MIT License
#---------------------------------------------------
*/

if (isset($_GET["QR"])) {
	include('GoogleAuthenticator.php');
	$g = new \GAuth\Auth();
	$code = $g->generateCode();
	echo "your new code is: ".$code;
	die();
}

$json = file_get_contents('php://input');
$post = json_decode($json,true);
if(!is_array($post)){
    die('Received content contained invalid JSON!');
}

$uid = $post["uid"];
$cmd = $post["cmd"];
$device_id = $post["device_id"];

if ((!isset($uid) && $cmd != "keyauth") ||  $cmd == "" || $device_id == "") {
	die('Not enough arguments! Sorry mate :)');
}

if (array_key_exists("key",$post)) {
	$key=$post["key"];
}
if (array_key_exists("doorcmd",$post)) {
        $doorcmd=$post["doorcmd"];
}
if (array_key_exists("gcode",$post)) {
	$gcode=$post["gcode"];
}

include('configuration.php');

$keys=json_decode(file_get_contents($json_rfid_userdb),true);

function generate_antitamper_txt($name,$num) {
	global $hmac_hash_key;
	return substr(hash_hmac('sha256', $name.$num, $hmac_hash_key),8,16);
}
function generate_keys_txt($name,$num) {
	global $hmac_hash_key;
    return substr(hash_hmac('sha256', $name.$num, $hmac_hash_key),8,12);
}
function check_antitamper_txt($name,$num,$txt) {
	if (generate_antitamper_txt($name,$num) == $txt) {
		return true;
	} else {
		return false;
	}
}



//for cloned cards:
if ($cmd=="chinauid" && $uid != "") {
	if (array_key_exists($uid,$keys)) {
		$name = $keys[$uid]["key_name"];
	} else {
		$name = "unknown";
	}
	china_uid_detected($device_id,$uid,$name);
	echo json_encode(array("status"=>"err"));
	return;
}

//Google Authenticator started without NFC (with PIN)
if ($cmd=="keyauth") {

	include('GoogleAuthenticator.php');
	if ($key != "" && strlen($key) == 10) {
			//key with pin
			//remove pin, search user
			$pin = substr($key,0,4);
			$googlecode = substr($key,4);
			$gauthkeys=json_decode(file_get_contents($json_gauth_userdb),true);
			if (array_key_exists($pin,$gauthkeys)) {
				$g = new \GAuth\Auth($gauthkeys[$pin]["GAuthSecret"]);

				$verify = $g->validateCode($googlecode);
				if ($verify) {
						door_toggle($device_id,$uid);
						echo json_encode(array("status"=>"kk"));
				} else {
						echo json_encode(array("status"=>"err"));
				}
				return;
			} else {
				echo json_encode(array("status"=>"err"));
				return;
			}
	}
	echo "sorry";
	return;

}

//NFC Authentication
//STAGE1: check if the tag UID is configured, if not write the ID to unknown_uids.txt
if ($cmd=="stage1" && $uid != "") {
	if (array_key_exists($uid,$keys)) {
	        if (array_key_exists("reset",$keys[$uid])) {
			resetfob($uid);
		} elseif (array_key_exists("anti_tamper_block_readkey",$keys[$uid])) {
			//if this key is allowed on the requested device OR if this user doesn't have any device_ids set
			if (!array_key_exists("device_ids",$keys[$uid]) || in_array("all",$keys[$uid]["device_ids"]) || in_array($device_id,$keys[$uid]["device_ids"])) {
				echo json_encode(array("status"=>"k","antiblk"=>$keys[$uid]["anti_tamper_block"],"key"=>$keys[$uid]["anti_tamper_block_readkey"],"len"=>$keys[$uid]["anti_tamper_len"]));
			} else {
				echo json_encode(array("status"=>"err","message"=>"You're not allowed on this device!"));
			}
		} elseif (array_key_exists("key_name",$keys[$uid]) && !array_key_exists("anti_tamper_block_readkey",$keys[$uid])) {
			initfob($uid);
		}

	} else {
		file_put_contents ($unknown_uid_log, date("Y-m-d H:i:s")." ".$uid."\n", FILE_APPEND);
		unknown_uid_detected($device_id,$uid);
		echo json_encode(array("status"=>"err"));
	}

//STAGE2: verify the stored key on the tag	
} elseif ($cmd=="stage2" && $uid != "" && $key != "") {
	if (array_key_exists($uid,$keys)) {
		if (check_antitamper_txt($keys[$uid]["key_name"],$keys[$uid]["anti_tamper_num"],$key)) {
			$newnum = rand();
			$newcode = generate_antitamper_txt($keys[$uid]["key_name"],$newnum);
			$keys[$uid]["anti_tamper_num_temp"] = $newnum;
                        $keys[$uid]["anti_tamper_temp_lastset"] = date("Y-m-d H:i:s");

			file_put_contents($json_rfid_userdb,json_encode($keys,JSON_PRETTY_PRINT));

			echo json_encode(array("status"=>"kk","setantiblk"=>$keys[$uid]["anti_tamper_block"],"key"=>$keys[$uid]["anti_tamper_block_writekey"],"txt"=>$newcode));

		} elseif (check_antitamper_txt($keys[$uid]["key_name"],$keys[$uid]["anti_tamper_num_temp"],$key)) {
			#on some rare race-condition if the user removes the fob at stage stage 3, the new value did get written to the fob but not to the local
			#database. So we check if the "temp" number is what the fob has stored and we adjust accordingly.
			$newnum = rand();
			$newcode = generate_antitamper_txt($keys[$uid]["key_name"],$newnum);
			$keys[$uid]["anti_tamper_num"] = $keys[$uid]["anti_tamper_num_temp"];
			$keys[$uid]["anti_tamper_num_temp"] = $newnum;
			$keys[$uid]["anti_tamper_temp_lastset"] = date("Y-m-d H:i:s");

			file_put_contents($json_rfid_userdb,json_encode($keys,JSON_PRETTY_PRINT));
			file_put_contents ("antitamper_temp_race_condition.txt", date("Y-m-d H:i:s")." ".$uid." ".$keys[$uid]["key_name"]."\n", FILE_APPEND);
			echo json_encode(array("status"=>"kk","setantiblk"=>$keys[$uid]["anti_tamper_block"],"key"=>$keys[$uid]["anti_tamper_block_writekey"],"txt"=>$newcode));

		} else {
			echo json_encode(array("status"=>"err"));
		}
    } else {
        echo json_encode(array("status"=>"err"));
	}

//STAGE3: Last stage for NFC Only authentication, verify the new key the fob has stored and open/close the door
} elseif ($cmd=="stage3" && $uid != "" && $key != "" && $doorcmd != "") {
        if (array_key_exists($uid,$keys)) {
                if (check_antitamper_txt($keys[$uid]["key_name"],$keys[$uid]["anti_tamper_num_temp"],$key)) {
					$keys[$uid]["anti_tamper_num"]=$keys[$uid]["anti_tamper_num_temp"];
					$keys[$uid]["last_use"] = date("Y-m-d H:i:s");
					$keys[$uid]["used_cnt"] += 1;
					file_put_contents($json_rfid_userdb,json_encode($keys,JSON_PRETTY_PRINT));

					if ($doorcmd == "open") {
						//if google authenticator is setup, ask for code
						if (array_key_exists("gauth_secret",$keys[$uid])) {
							//if PIN is also setup, tell the reader to ask for 10 numbers (6 GAuth + 4 PIN)
							if (array_key_exists("gauth_pin",$keys[$uid])) {
								$req_gauth_numbers = 10;
							} else {
								//else, ask the reader for 6 numbers
								$req_gauth_numbers = 6;
							}
							echo json_encode(array("status"=>"getcode","num" => $req_gauth_numbers));
						//If PIN + NFC is setup
						} elseif (array_key_exists("nfc_pin",$keys[$uid])) {
							$req_gauth_numbers = 4;
							echo json_encode(array("status"=>"getcode","num" => $req_gauth_numbers));
						} else {
							door_open($device_id,$uid);
							echo json_encode(array("status"=>"done"));
						}

					} elseif ($doorcmd == "close") {
						door_close($device_id,$uid);
						echo json_encode(array("status"=>"done"));
					}
				} else {
                    echo json_encode(array("status"=>"err"));
                }
        } else {
                echo json_encode(array("status"=>"err"));
        }

//STAGE4: Last stage for NFC+Google Auth Authentication, verify the key on the tag again + verify GoogleAuth Key and PIN(if configured), then open/close the door
} elseif ($cmd=="stage4" && $uid != "" && $key != "" && $doorcmd != "" && $gcode != "") {
	if (array_key_exists($uid,$keys)) {
			if (check_antitamper_txt($keys[$uid]["key_name"],$keys[$uid]["anti_tamper_num"],$key)) {
				
				//NFC + GAuth
				if (array_key_exists("gauth_secret",$keys[$uid])) {
					if (array_key_exists("gauth_pin",$keys[$uid])) {
						$pin = substr($gcode,0,4);
						$googlecode = substr($gcode,4);
						if ($pin != $keys[$uid]["gauth_pin"]) {
							echo json_encode(array("status"=>"err"));
							return;
						}
					} else {
						$googlecode = $gcode;
					}
					include('GoogleAuthenticator.php');
					$g = new \GAuth\Auth($keys[$uid]["gauth_secret"]);
		
					$verify = $g->validateCode($gcode);
					if ($verify) {

						if ($doorcmd == "open") {
							door_open($device_id,$uid);
							echo json_encode(array("status"=>"done"));
						

						} elseif ($doorcmd == "close") {
							door_close($device_id,$uid);
							echo json_encode(array("status"=>"done"));
						}
					} else {
						echo json_encode(array("status"=>"err"));
					}
				
				//NFC + PIN
				} elseif (array_key_exists("nfc_pin",$keys[$uid])) {
					$pin = substr($gcode,0,4);
					if ($pin != $keys[$uid]["nfc_pin"]) {
						echo json_encode(array("status"=>"err"));
						return;
					} else {
						if ($doorcmd == "open") {
							door_open($device_id,$uid);
							echo json_encode(array("status"=>"done"));
						

						} elseif ($doorcmd == "close") {
							door_close($device_id,$uid);
							echo json_encode(array("status"=>"done"));
						}						
					}					
				}
			} else {
				echo json_encode(array("status"=>"err"));
			}
	} else {
			echo json_encode(array("status"=>"err"));
	}
}

function resetfob($uid) {
	global $keys, $json_rfid_userdb;
	echo json_encode(array("status"=>"reset","keya" => $keys[$uid]["keya"],"keyb" => $keys[$uid]["keyb"]));
	$name =  $keys[$uid]["key_name"];
	
	//save Google AUthenticator data if it is setup
	$gauth = array();
	if (array_key_exists("gauth_pin",$keys[$uid])) {
		$gauth["gauth_pin"] = $keys[$uid]["gauth_pin"];
	}
	if (array_key_exists("gauth_secret",$keys[$uid])) {
		$gauth["gauth_secret"] = $keys[$uid]["gauth_secret"];
	}	
	if (array_key_exists("nfc_pin",$keys[$uid])) {
		$gauth["nfc_pin"] = $keys[$uid]["nfc_pin"];
	}	
	
	//remove all other data
	unset($keys[$uid]);
	//write back name to json file
	$keys[$uid]["key_name"] = $name;
	
	//Write back Google Authenticator data if it was setup
	if (array_key_exists("gauth_pin",$gauth)) {
		$keys[$uid]["gauth_pin"] = $gauth["gauth_pin"];
	}
	if (array_key_exists("gauth_secret",$gauth)) {
		$keys[$uid]["gauth_secret"] = $gauth["gauth_secret"];
	}
	if (array_key_exists("nfc_pin",$gauth)) {
		$keys[$uid]["nfc_pin"] = $gauth["nfc_pin"];
	}	

	//write file
	file_put_contents($json_rfid_userdb,json_encode($keys,JSON_PRETTY_PRINT));
}
function get_rand_block_to_write() {
	//we need to ensure that we dont write to block 4 of any sector as this is reserved for Key and Access control.
	// and we cannot use sector 0, so we have sector 1-15 (for 16 sectors)
	$sector = rand(1,15);
	$block = rand(0,2);

	return ($sector*4)+$block;
}


//generate random data to fill the card
function get_rand_filler() {
	$charset = "0123456789abcdef";

	//16 sectors
	for ($i = 0; $i < 15; $i++) {
		//4 possible blocks each (but only 3 get used)
		for ($b = 0; $b < 4; $b++) {
			//16 bytes each
			$tmp_randstr = "";
			for ($x = 0; $x < 16; $x++) {
				$tmp_randstr .= $charset[rand(0, strlen($charset)-1)];
			}
			$randstr[] = $tmp_randstr;
		}
	}
	return $randstr;
}

//initialize a new keyfob / tag
function initfob($uid) {
	global $keys,$json_rfid_userdb;
    if (array_key_exists($uid,$keys)) {
		if (array_key_exists("key_name",$keys[$uid])) {
			if (!array_key_exists("anti_tamper_block_readkey",$keys[$uid])) {
				//$keys[$uid]["anti_tamper_block"] = 8; // static block to write
				$keys[$uid]["anti_tamper_block"] = get_rand_block_to_write(); // random block to write
				$keys[$uid]["anti_tamper_num"] = 3;
				$keys[$uid]["anti_tamper_len"] = 8;
				$keys[$uid]["used_cnt"] = 1;
				for ($i=1;$i<=16;$i++) {
					$keys[$uid]["keya"][] = generate_keys_txt($keys[$uid]["key_name"],rand());
					//$keys[$uid]["keya"][] = "a0a1a2a3a4a5"; //DEV! Use this if you want to read the tag with a mobile to test if everything works
				}
	            for ($i=1;$i<=16;$i++) {
	            	$keys[$uid]["keyb"][] = generate_keys_txt($keys[$uid]["key_name"],rand());
					//$keys[$uid]["keyb"][] = "a0a1a2a3a4a5"; //DEV! Use this if you want to read the tag with a mobile to test if everything works
	        	}
	            $keys[$uid]["anti_tamper_block_readkey"] = $keys[$uid]["keya"][(int)($keys[$uid]["anti_tamper_block"]/4)]; //correct key for sector  - [60 == sector 15 || 59 == sector 14]
	            $keys[$uid]["anti_tamper_block_writekey"] = $keys[$uid]["keyb"][(int)($keys[$uid]["anti_tamper_block"]/4)]; //correct key for sector  - [60 == sector 15 || 59 == sector 14]
				//print_r($keys);
	            $newnum = rand();
				$newcode = generate_antitamper_txt($keys[$uid]["key_name"],$newnum);
				$keys[$uid]["anti_tamper_num"] =$newnum;
				file_put_contents($json_rfid_userdb,json_encode($keys,JSON_PRETTY_PRINT));
				
				//generate (pseudo)random chars between 0 and f to fill the card
				$randfill = get_rand_filler();
				echo json_encode(array("status"=>"init","setantiblk"=>$keys[$uid]["anti_tamper_block"],"key"=>$keys[$uid]["anti_tamper_block_writekey"],"txt"=>$newcode,"keya" => $keys[$uid]["keya"],"keyb" => $keys[$uid]["keyb"], "filler" => $randfill));

			} else {
				echo json_encode(array("status"=>"err", "message" => "uid already populated (:"));
			}
		} else {
			echo json_encode(array("status"=>"err", "message" => "key_name not defined!"));
		}
	} else {
		echo json_encode(array("status"=>"err", "message" => "uid not defined"));
	}
}

?>
