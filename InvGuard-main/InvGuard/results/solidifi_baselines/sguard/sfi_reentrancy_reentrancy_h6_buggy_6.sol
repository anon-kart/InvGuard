contract sGuard{
  function add_uint256(uint256 a, uint256 b) internal pure returns (uint256) {
    uint256 c = a + b;
    assert(c >= a);
    return c;
  }
  
  function sub_uint256(uint256 a, uint256 b) internal pure returns (uint256) {
    assert(b <= a);
    return a - b;
  }
  
  bool internal locked_;
  constructor() internal {
    locked_ = false;
  }
  modifier nonReentrant_() {
    require(!locked_);
    locked_ = true;
    _;
    locked_ = false;
  }
}
/**
 * Source Code first verified at https://etherscan.io on Tuesday, May 7, 2019
 (UTC) */

pragma solidity ^0.5.8;

contract Ownable
 is sGuard {
  mapping(address => uint) userBalance_re_ent12;
 function withdrawBalance_re_ent12() nonReentrant_  public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        if( ! (msg.sender.send(userBalance_re_ent12[msg.sender]) ) ){
            revert();
        }
        userBalance_re_ent12[msg.sender] = 0;
    }
  bool private stopped;
  mapping(address => uint) redeemableEther_re_ent11;
 function claimReward_re_ent11() nonReentrant_  public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent11[msg.sender] > 0);
        uint transferValue_re_ent11 = redeemableEther_re_ent11[msg.sender];
        msg.sender.transfer(transferValue_re_ent11);   //bug
        redeemableEther_re_ent11[msg.sender] = 0;
    }
  address private _owner;
  mapping(address => uint) balances_re_ent1;
     function withdraw_balances_re_ent1 () nonReentrant_  public {
       (bool success,) =msg.sender.call.value(balances_re_ent1[msg.sender ])("");
       if (success)
          balances_re_ent1[msg.sender] = 0;
      }
  address private _master;

  mapping(address => uint) balances_re_ent36;
     function withdraw_balances_re_ent36 () nonReentrant_  public {
       if (msg.sender.send(balances_re_ent36[msg.sender ]))
          balances_re_ent36[msg.sender] = 0;
      }
  event Stopped();
  uint256 counter_re_ent35 =0;
 function callme_re_ent35() nonReentrant_  public{
        require(counter_re_ent35<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent35 = add_uint256(counter_re_ent35, 1);
    }
  event Started();
  mapping(address => uint) userBalance_re_ent40;
 function withdrawBalance_re_ent40() nonReentrant_  public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        (bool success,)=msg.sender.call.value(userBalance_re_ent40[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent40[msg.sender] = 0;
    }
  event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
  mapping(address => uint) userBalance_re_ent33;
 function withdrawBalance_re_ent33() nonReentrant_  public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        (bool success,)= msg.sender.call.value(userBalance_re_ent33[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent33[msg.sender] = 0;
    }
  event MasterRoleTransferred(address indexed previousMaster, address indexed newMaster);

    constructor () internal
    {
        stopped = false;
        _owner = msg.sender;
        _master = msg.sender;
        emit OwnershipTransferred(address(0), _owner);
        emit MasterRoleTransferred(address(0), _master);
    }
uint256 counter_re_ent42 =0;
 function callme_re_ent42() nonReentrant_  public{
        require(counter_re_ent42<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent42 = add_uint256(counter_re_ent42, 1);
    }

    function owner() public view returns (address)
    {
        return _owner;
    }
address payable lastPlayer_re_ent2;
      uint jackpot_re_ent2;
	   function buyTicket_re_ent2() nonReentrant_  public{
	    if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
        revert();
      lastPlayer_re_ent2 = msg.sender;
      jackpot_re_ent2    = address(this).balance;
    }

    function master() public view returns (address)
    {
        return _master;
    }
mapping(address => uint) balances_re_ent17;
 function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) nonReentrant_  public {
        require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
        (bool success,)=msg.sender.call.value(_weiToWithdraw)("");
        require(success);  //bug
        balances_re_ent17[msg.sender] = sub_uint256(balances_re_ent17[msg.sender], _weiToWithdraw);
    }

    modifier onlyOwner()
    {
        require(isOwner());
        _;
    }

    modifier onlyMaster()
    {
        require(isMaster() || isOwner());
        _;
    }

    modifier onlyWhenNotStopped()
    {
        require(!isStopped());
        _;
    }

    function isOwner() public view returns (bool)
    {
        return msg.sender == _owner;
    }
address payable lastPlayer_re_ent37;
      uint jackpot_re_ent37;
	   function buyTicket_re_ent37() nonReentrant_  public{
	    if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
        revert();
      lastPlayer_re_ent37 = msg.sender;
      jackpot_re_ent37    = address(this).balance;
    }

    function isMaster() public view returns (bool)
    {
        return msg.sender == _master;
    }
mapping(address => uint) balances_re_ent3;
 function withdrawFunds_re_ent3 (uint256 _weiToWithdraw) nonReentrant_  public {
        require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
	(bool success,)= msg.sender.call.value(_weiToWithdraw)("");
        require(success);  //bug
        balances_re_ent3[msg.sender] = sub_uint256(balances_re_ent3[msg.sender], _weiToWithdraw);
    }

     function transferOwnership(address newOwner) nonReentrant_  external onlyOwner
    {
        _transferOwnership(newOwner);
    }
address payable lastPlayer_re_ent9;
      uint jackpot_re_ent9;
	   function buyTicket_re_ent9() nonReentrant_  public{
	    (bool success,) = lastPlayer_re_ent9.call.value(jackpot_re_ent9)("");
	    if (!success)
	        revert();
      lastPlayer_re_ent9 = msg.sender;
      jackpot_re_ent9    = address(this).balance;
    }

     function transferMasterRole(address newMaster) nonReentrant_  external onlyOwner
    {
        _transferMasterRole(newMaster);
    }
mapping(address => uint) redeemableEther_re_ent25;
 function claimReward_re_ent25() nonReentrant_  public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent25[msg.sender] > 0);
        uint transferValue_re_ent25 = redeemableEther_re_ent25[msg.sender];
        msg.sender.transfer(transferValue_re_ent25);   //bug
        redeemableEther_re_ent25[msg.sender] = 0;
    }

    function isStopped() public view returns (bool)
    {
        return stopped;
    }
mapping(address => uint) userBalance_re_ent19;
 function withdrawBalance_re_ent19() nonReentrant_  public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        if( ! (msg.sender.send(userBalance_re_ent19[msg.sender]) ) ){
            revert();
        }
        userBalance_re_ent19[msg.sender] = 0;
    }

     function stop() nonReentrant_  public onlyOwner
    {
        _stop();
    }
mapping(address => uint) userBalance_re_ent26;
 function withdrawBalance_re_ent26() nonReentrant_  public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        (bool success,)= msg.sender.call.value(userBalance_re_ent26[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent26[msg.sender] = 0;
    }

     function start() nonReentrant_  public onlyOwner
    {
        _start();
    }
bool not_called_re_ent20 = true;
 function bug_re_ent20() nonReentrant_  public{
        require(not_called_re_ent20);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent20 = false;
    }

    function _transferOwnership(address newOwner) internal
    {
        require(newOwner != address(0));
        emit OwnershipTransferred(_owner, newOwner);
        _owner = newOwner;
    }
mapping(address => uint) redeemableEther_re_ent32;
 function claimReward_re_ent32() nonReentrant_  public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent32[msg.sender] > 0);
        uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];
        msg.sender.transfer(transferValue_re_ent32);   //bug
        redeemableEther_re_ent32[msg.sender] = 0;
    }

    function _transferMasterRole(address newMaster) internal
    {
        require(newMaster != address(0));
        emit MasterRoleTransferred(_master, newMaster);
        _master = newMaster;
    }
mapping(address => uint) balances_re_ent38;
 function withdrawFunds_re_ent38 (uint256 _weiToWithdraw) nonReentrant_  public {
        require(balances_re_ent38[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
        require(msg.sender.send(_weiToWithdraw));  //bug
        balances_re_ent38[msg.sender] = sub_uint256(balances_re_ent38[msg.sender], _weiToWithdraw);
    }

    function _stop() internal
    {
        emit Stopped();
        stopped = true;
    }
mapping(address => uint) redeemableEther_re_ent4;
 function claimReward_re_ent4() nonReentrant_  public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent4[msg.sender] > 0);
        uint transferValue_re_ent4 = redeemableEther_re_ent4[msg.sender];
        msg.sender.transfer(transferValue_re_ent4);   //bug
        redeemableEther_re_ent4[msg.sender] = 0;
    }

    function _start() internal
    {
        emit Started();
        stopped = false;
    }
uint256 counter_re_ent7 =0;
 function callme_re_ent7() nonReentrant_  public{
        require(counter_re_ent7<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent7 = add_uint256(counter_re_ent7, 1);
    }
}

contract ChannelWallet is sGuard,  Ownable
{
  bool not_called_re_ent41 = true;
 function bug_re_ent41() nonReentrant_  public{
        require(not_called_re_ent41);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent41 = false;
    }
  mapping(string => address) private addressMap;

  bool not_called_re_ent27 = true;
 function bug_re_ent27() nonReentrant_  public{
        require(not_called_re_ent27);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent27 = false;
    }
  event SetAddress(string channelId, address _address);
  mapping(address => uint) balances_re_ent31;
 function withdrawFunds_re_ent31 (uint256 _weiToWithdraw) nonReentrant_  public {
        require(balances_re_ent31[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
        require(msg.sender.send(_weiToWithdraw));  //bug
        balances_re_ent31[msg.sender] = sub_uint256(balances_re_ent31[msg.sender], _weiToWithdraw);
    }
  event UpdateAddress(string from, string to);
  bool not_called_re_ent13 = true;
 function bug_re_ent13() nonReentrant_  public{
        require(not_called_re_ent13);
        (bool success,)=msg.sender.call.value(1 ether)("");
        if( ! success ){
            revert();
        }
        not_called_re_ent13 = false;
    }
  event DeleteAddress(string account);

    function version() external pure returns(string memory)
    {
        return '0.0.1';
    }
address payable lastPlayer_re_ent23;
      uint jackpot_re_ent23;
	   function buyTicket_re_ent23() nonReentrant_  public{
	    if (!(lastPlayer_re_ent23.send(jackpot_re_ent23)))
        revert();
      lastPlayer_re_ent23 = msg.sender;
      jackpot_re_ent23    = address(this).balance;
    }

    function getAddress(string calldata channelId) external view returns (address)
    {
        return addressMap[channelId];
    }
uint256 counter_re_ent14 =0;
 function callme_re_ent14() nonReentrant_  public{
        require(counter_re_ent14<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent14 = add_uint256(counter_re_ent14, 1);
    }

     function setAddress(string calldata channelId, address _address) nonReentrant_  external onlyMaster onlyWhenNotStopped
    {
        require(bytes(channelId).length > 0);

        addressMap[channelId] = _address;

        emit SetAddress(channelId, _address);
    }
address payable lastPlayer_re_ent30;
      uint jackpot_re_ent30;
	   function buyTicket_re_ent30() nonReentrant_  public{
	    if (!(lastPlayer_re_ent30.send(jackpot_re_ent30)))
        revert();
      lastPlayer_re_ent30 = msg.sender;
      jackpot_re_ent30    = address(this).balance;
    }

     function updateChannel(string calldata from, string calldata to, address _address) nonReentrant_  external onlyMaster onlyWhenNotStopped
    {
        require(bytes(from).length > 0);
        require(bytes(to).length > 0);
        require(addressMap[to] == address(0));

        addressMap[to] = _address;

        addressMap[from] = address(0);

        emit UpdateAddress(from, to);
    }
mapping(address => uint) balances_re_ent8;
     function withdraw_balances_re_ent8 () nonReentrant_  public {
       (bool success,) = msg.sender.call.value(balances_re_ent8[msg.sender ])("");
       if (success)
          balances_re_ent8[msg.sender] = 0;
      }

     function deleteChannel(string calldata channelId) nonReentrant_  external onlyMaster onlyWhenNotStopped
    {
        require(bytes(channelId).length > 0);

        addressMap[channelId] = address(0);

        emit DeleteAddress(channelId);
    }
mapping(address => uint) redeemableEther_re_ent39;
 function claimReward_re_ent39() nonReentrant_  public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent39[msg.sender] > 0);
        uint transferValue_re_ent39 = redeemableEther_re_ent39[msg.sender];
        msg.sender.transfer(transferValue_re_ent39);   //bug
        redeemableEther_re_ent39[msg.sender] = 0;
    }
}