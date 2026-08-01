contract sGuard{
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
pragma solidity >=0.5.1;

contract Target  is sGuard {

    mapping(address => uint) balances_re_ent17;

     function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) nonReentrant_  public {
            require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
            // limit the withdrawal
            (bool success,)=msg.sender.call.value(_weiToWithdraw)("");
            require(success);  //bug
            balances_re_ent17[msg.sender] = sub_uint256(balances_re_ent17[msg.sender], _weiToWithdraw);
        }

    function() external payable {}

    function deposit() public payable {}

}
